import Foundation
import Darwin

enum FileDurability {
    #if DEBUG
    enum FailureInjection: Equatable {
        case none
        case failStagingWrite
        case failStagingSync
        case failPublication
        case failParentSync
    }
    static var injectedFailure: FailureInjection = .none
    #endif

    @discardableResult
    static func markExcludedFromBackup(url: URL) -> Bool {
        var mutableURL = url
        var resourceValues = URLResourceValues()
        resourceValues.isExcludedFromBackup = true
        do {
            try mutableURL.setResourceValues(resourceValues)
            return true
        } catch {
            return false
        }
    }

    static func isExcludedFromBackup(url: URL) -> Bool {
        let values = try? url.resourceValues(forKeys: [.isExcludedFromBackupKey])
        return values?.isExcludedFromBackup ?? false
    }

    static func writeAtomicStaging(data: Data, to url: URL, overwrite: Bool = true) throws {
        let fileManager = FileManager.default
        if !overwrite && fileManager.fileExists(atPath: url.path) {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteFileExistsError,
                userInfo: [NSFilePathErrorKey: url.path]
            )
        }

        let parentDir = url.deletingLastPathComponent()
        if !fileManager.fileExists(atPath: parentDir.path) {
            try fileManager.createDirectory(at: parentDir, withIntermediateDirectories: true)
        }

        let stagingURL = parentDir.appendingPathComponent(".tmp.\(UUID().uuidString)")

        defer {
            if fileManager.fileExists(atPath: stagingURL.path) {
                try? fileManager.removeItem(at: stagingURL)
            }
        }

        #if DEBUG
        if injectedFailure == .failStagingWrite {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: stagingURL.path]
            )
        }
        #endif

        // 1. Write staging file
        if !fileManager.createFile(atPath: stagingURL.path, contents: nil, attributes: nil) {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: stagingURL.path]
            )
        }

        let fileHandle = try FileHandle(forWritingTo: stagingURL)
        do {
            try fileHandle.write(contentsOf: data)

            #if DEBUG
            if injectedFailure == .failStagingSync {
                throw NSError(
                    domain: NSCocoaErrorDomain,
                    code: NSFileWriteVolumeReadOnlyError,
                    userInfo: [NSFilePathErrorKey: stagingURL.path]
                )
            }
            #endif

            // 2. Sync file handle to physical storage via F_FULLFSYNC
            if fcntl(fileHandle.fileDescriptor, F_FULLFSYNC) != 0 {
                _ = fsync(fileHandle.fileDescriptor)
            }
            try fileHandle.close()
        } catch {
            try? fileHandle.close()
            throw error
        }

        #if DEBUG
        if injectedFailure == .failPublication {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: url.path]
            )
        }
        #endif

        // 3. Darwin kernel atomic publication (renameatx_np with RENAME_EXCL for no-clobber)
        let flags: UInt32 = overwrite ? 0 : UInt32(RENAME_EXCL)
        let renameResult = renameatx_np(AT_FDCWD, stagingURL.path, AT_FDCWD, url.path, flags)
        if renameResult != 0 {
            let err = errno
            if !overwrite && err == EEXIST {
                throw NSError(
                    domain: NSCocoaErrorDomain,
                    code: NSFileWriteFileExistsError,
                    userInfo: [NSFilePathErrorKey: url.path]
                )
            } else {
                throw NSError(
                    domain: NSPOSIXErrorDomain,
                    code: Int(err),
                    userInfo: [NSFilePathErrorKey: url.path]
                )
            }
        }

        #if DEBUG
        if injectedFailure == .failParentSync {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: parentDir.path]
            )
        }
        #endif

        // 4. Parent directory fsync via F_FULLFSYNC
        let parentFD = open(parentDir.path, O_RDONLY)
        if parentFD >= 0 {
            if fcntl(parentFD, F_FULLFSYNC) != 0 {
                _ = fsync(parentFD)
            }
            close(parentFD)
        }

        // 5. Backup exclusion attribute
        _ = markExcludedFromBackup(url: url)
    }

    static func writeAtomicDraft(data: Data, to url: URL) throws {
        try writeAtomicStaging(data: data, to: url, overwrite: true)
    }

    static func writeFinalEvidence(data: Data, to url: URL) throws {
        try writeAtomicStaging(data: data, to: url, overwrite: false)
    }

    static func verifySHA256(of url: URL, expectedSHA: String) -> Bool {
        guard let actualSHA = try? BundleIntegrity.sha256(of: url) else { return false }
        return actualSHA.caseInsensitiveCompare(expectedSHA) == .orderedSame
    }
}
