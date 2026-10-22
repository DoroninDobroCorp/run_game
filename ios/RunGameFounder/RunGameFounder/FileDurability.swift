import Foundation
import Darwin

enum FileDurability {
    #if DEBUG
    enum FailureInjection: Equatable {
        case none
        case failStagingWrite
        case failStagingSync
        case failFallbackFsync
        case failBackupExclusion
        case failPublication
        case failParentOpen
        case failParentSync
    }
    nonisolated(unsafe) static var injectedFailure: FailureInjection = .none
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
                #if DEBUG
                if injectedFailure == .failFallbackFsync {
                    throw NSError(
                        domain: NSPOSIXErrorDomain,
                        code: Int(EIO),
                        userInfo: [NSFilePathErrorKey: stagingURL.path, NSLocalizedDescriptionKey: "Injected fallback fsync failure"]
                    )
                }
                #endif
                if fsync(fileHandle.fileDescriptor) != 0 {
                    let err = errno
                    throw NSError(
                        domain: NSPOSIXErrorDomain,
                        code: Int(err),
                        userInfo: [NSFilePathErrorKey: stagingURL.path, NSLocalizedDescriptionKey: "Fallback fsync failed"]
                    )
                }
            } else {
                #if DEBUG
                if injectedFailure == .failFallbackFsync {
                    throw NSError(
                        domain: NSPOSIXErrorDomain,
                        code: Int(EIO),
                        userInfo: [NSFilePathErrorKey: stagingURL.path, NSLocalizedDescriptionKey: "Injected fallback fsync failure"]
                    )
                }
                #endif
            }
            try fileHandle.close()
        } catch {
            try? fileHandle.close()
            throw error
        }

        // 3. Mark temporary staging file as excluded from backup BEFORE publication
        #if DEBUG
        if injectedFailure == .failBackupExclusion {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: stagingURL.path, NSLocalizedDescriptionKey: "Injected backup exclusion failure"]
            )
        }
        #endif

        guard markExcludedFromBackup(url: stagingURL) else {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: stagingURL.path, NSLocalizedDescriptionKey: "Failed to mark staging file as excluded from backup"]
            )
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

        // 4. Darwin kernel atomic publication (renameatx_np with RENAME_EXCL for no-clobber)
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
        if injectedFailure == .failParentOpen {
            throw NSError(
                domain: NSPOSIXErrorDomain,
                code: Int(ENOENT),
                userInfo: [NSFilePathErrorKey: parentDir.path, NSLocalizedDescriptionKey: "Injected parent dir open failure"]
            )
        }
        #endif

        // 5. Parent directory fsync via F_FULLFSYNC
        let parentFD = open(parentDir.path, O_RDONLY)
        if parentFD < 0 {
            let err = errno
            throw NSError(
                domain: NSPOSIXErrorDomain,
                code: Int(err),
                userInfo: [NSFilePathErrorKey: parentDir.path, NSLocalizedDescriptionKey: "Failed to open parent directory for fsync"]
            )
        }
        defer {
            close(parentFD)
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

        if fcntl(parentFD, F_FULLFSYNC) != 0 {
            if fsync(parentFD) != 0 {
                let err = errno
                throw NSError(
                    domain: NSPOSIXErrorDomain,
                    code: Int(err),
                    userInfo: [NSFilePathErrorKey: parentDir.path, NSLocalizedDescriptionKey: "Failed to sync parent directory"]
                )
            }
        }

        // 6. Backup exclusion attribute
        guard markExcludedFromBackup(url: url) else {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteUnknownError,
                userInfo: [NSFilePathErrorKey: url.path, NSLocalizedDescriptionKey: "Failed to mark published file as excluded from backup"]
            )
        }
    }

    static func writeAtomicDraft(data: Data, to url: URL) throws {
        try writeAtomicStaging(data: data, to: url, overwrite: true)
    }

    static func writeFinalEvidence(data: Data, to url: URL) throws {
        try writeAtomicStaging(data: data, to: url, overwrite: false)
    }

    static func removeDurably(at url: URL) throws {
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: url.path) else { return }
        try fileManager.removeItem(at: url)

        let parentDir = url.deletingLastPathComponent()
        let parentFD = open(parentDir.path, O_RDONLY)
        if parentFD < 0 {
            let err = errno
            throw NSError(
                domain: NSPOSIXErrorDomain,
                code: Int(err),
                userInfo: [NSFilePathErrorKey: parentDir.path, NSLocalizedDescriptionKey: "Failed to open parent directory after removal"]
            )
        }
        defer { close(parentFD) }

        if fcntl(parentFD, F_FULLFSYNC) != 0, fsync(parentFD) != 0 {
            let err = errno
            throw NSError(
                domain: NSPOSIXErrorDomain,
                code: Int(err),
                userInfo: [NSFilePathErrorKey: parentDir.path, NSLocalizedDescriptionKey: "Failed to sync parent directory after removal"]
            )
        }
    }

    static func verifySHA256(of url: URL, expectedSHA: String) -> Bool {
        guard let actualSHA = try? BundleIntegrity.sha256(of: url) else { return false }
        return actualSHA.caseInsensitiveCompare(expectedSHA) == .orderedSame
    }
}
