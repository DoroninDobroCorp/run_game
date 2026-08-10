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
        try data.write(to: url, options: .withoutOverwriting)
        _ = markExcludedFromBackup(url: url)
    }

    static func verifySHA256(of url: URL, expectedSHA: String) -> Bool {
        guard let actualSHA = try? BundleIntegrity.sha256(of: url) else { return false }
        return actualSHA.caseInsensitiveCompare(expectedSHA) == .orderedSame
    }
}
