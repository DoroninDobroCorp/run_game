import Foundation

enum FileDurability {
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

        // 1. Write staging file
        fileManager.createFile(atPath: stagingURL.path, contents: nil, attributes: nil)
        let fileHandle = try FileHandle(forWritingTo: stagingURL)
        defer {
            try? fileHandle.close()
        }

        try fileHandle.write(contentsOf: data)
        // 2. Sync file handle to physical storage
        try fileHandle.synchronize()

        // 3. Atomic rename / replace
        if fileManager.fileExists(atPath: url.path) {
            _ = try fileManager.replaceItemAt(url, withItemAt: stagingURL)
        } else {
            try fileManager.moveItem(at: stagingURL, to: url)
        }

        // 4. Parent directory fsync
        let parentFD = open(parentDir.path, O_RDONLY)
        if parentFD >= 0 {
            _ = fcntl(parentFD, F_FULLFSYNC)
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
