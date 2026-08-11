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

    static func writeAtomicDraft(data: Data, to url: URL) throws {
        try data.write(to: url, options: .atomic)
        _ = markExcludedFromBackup(url: url)
    }

    static func writeFinalEvidence(data: Data, to url: URL) throws {
        // Enforce fail-closed overwrite protection
        let fileManager = FileManager.default
        guard !fileManager.fileExists(atPath: url.path) else {
            throw NSError(
                domain: NSCocoaErrorDomain,
                code: NSFileWriteFileExistsError,
                userInfo: [NSFilePathErrorKey: url.path]
            )
        }

        let parentDir = url.deletingLastPathComponent()
        let stagingURL = parentDir.appendingPathComponent(".tmp.\(UUID().uuidString)")

        // 1. Write staging file
        fileManager.createFile(atPath: stagingURL.path, contents: nil, attributes: nil)
        let fileHandle = try FileHandle(forWritingTo: stagingURL)
        defer {
            try? fileHandle.close()
        }

        try fileHandle.write(contentsOf: data)
        // 2. Sync to physical storage
        try fileHandle.synchronize()

        // 3. Atomic rename / replace
        _ = try fileManager.replaceItemAt(url, withItemAt: stagingURL)

        _ = markExcludedFromBackup(url: url)
    }

    static func verifySHA256(of url: URL, expectedSHA: String) -> Bool {
        guard let actualSHA = try? BundleIntegrity.sha256(of: url) else { return false }
        return actualSHA.caseInsensitiveCompare(expectedSHA) == .orderedSame
    }
}
