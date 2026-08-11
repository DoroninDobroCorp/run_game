import XCTest
@testable import RunGameFounder

final class FileDurabilityTests: XCTestCase {
    private var tempDirectory: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        tempDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent("FileDurabilityTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tempDirectory, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        if tempDirectory != nil {
            try? FileManager.default.removeItem(at: tempDirectory)
        }
        try super.tearDownWithError()
    }

    func testAtomicDraftWriteAndBackupExclusion() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-draft.json")
        let draftData = Data("{\"status\": \"draft\"}".utf8)

        try FileDurability.writeAtomicDraft(data: draftData, to: fileURL)

        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, draftData)
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))
    }

    func testFinalEvidenceWithoutOverwritingProtection() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-final-evidence.json")
        let initialData = Data("{\"status\": \"initial\"}".utf8)
        let replacementData = Data("{\"status\": \"replacement\"}".utf8)

        try FileDurability.writeFinalEvidence(data: initialData, to: fileURL)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))

        XCTAssertThrowsError(
            try FileDurability.writeFinalEvidence(data: replacementData, to: fileURL)
        ) { error in
            let nsError = error as NSError
            XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
            XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
        }

        let preservedData = try Data(contentsOf: fileURL)
        XCTAssertEqual(preservedData, initialData)
    }

    func testFinalEvidenceStagingSyncAndAtomicRename() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-staging-final.json")
        let finalData = Data("{\"status\": \"staged_and_synced\"}".utf8)

        try FileDurability.writeFinalEvidence(data: finalData, to: fileURL)
        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path))

        // Check content
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, finalData)
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))

        // Verify temporary staging file (.tmp.<uuid>) is no longer present in directory
        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty)
    }

    func testSHA256VerificationBeforeApproval() throws {
        let fileURL = tempDirectory.appendingPathComponent("test-track.gpx")
        let trackData = Data("<gpx><trk></trk></gpx>".utf8)
        try FileDurability.writeAtomicDraft(data: trackData, to: fileURL)

        let expectedSHA = BundleIntegrity.sha256(of: trackData)
        XCTAssertTrue(FileDurability.verifySHA256(of: fileURL, expectedSHA: expectedSHA))

        let tamperedData = Data("<gpx><trk>TAMPERED</trk></gpx>".utf8)
        try tamperedData.write(to: fileURL, options: .atomic)
        XCTAssertFalse(FileDurability.verifySHA256(of: fileURL, expectedSHA: expectedSHA))
    }

    @MainActor
    func testCorruptedQueueInAppModelFailsClosed() throws {
        let suiteName = "FileDurabilityTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let queueKeyBytes: [UInt8] = [102, 111, 117, 110, 100, 101, 114, 46, 118, 50, 46, 112, 101, 110, 100, 105, 110, 103, 68, 101, 98, 114, 105, 101, 102, 115]
        let debriefKey = String(bytes: queueKeyBytes, encoding: .utf8)!
        defaults.set(Data("corrupted json data".utf8), forKey: debriefKey)

        let model = AppModel(defaults: defaults)

        XCTAssertTrue(model.queueCorrupted)
        XCTAssertTrue(model.evidenceCaptureLocked)
    }

    func testConcurrentAtomicWrites() throws {
        let iterations = 20
        let expectation = expectation(description: "Concurrent atomic writes complete")
        expectation.expectedFulfillmentCount = iterations

        let targetDir = tempDirectory!

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let fileURL = targetDir.appendingPathComponent("concurrent-\(index).json")
            let data = Data("{\"index\": \(index)}".utf8)
            do {
                try FileDurability.writeAtomicDraft(data: data, to: fileURL)
                let readData = try Data(contentsOf: fileURL)
                XCTAssertEqual(readData, data)
                XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL))
            } catch {
                XCTFail("Concurrent write failed for index \(index): \(error)")
            }
            expectation.fulfill()
        }

        waitForExpectations(timeout: 10.0)

        let files = try FileManager.default.contentsOfDirectory(atPath: targetDir.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    func testConcurrentOverwriteProtection() throws {
        let fileURL = tempDirectory.appendingPathComponent("concurrent-overwrite.json")
        let initialData = Data("{\"status\": \"initial\"}".utf8)
        try FileDurability.writeFinalEvidence(data: initialData, to: fileURL)

        let iterations = 20
        let expectation = expectation(description: "Concurrent overwrite attempts complete")
        expectation.expectedFulfillmentCount = iterations

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let replacementData = Data("{\"status\": \"replacement-\(index)\"}".utf8)
            do {
                try FileDurability.writeFinalEvidence(data: replacementData, to: fileURL)
                XCTFail("writeFinalEvidence should have thrown NSFileWriteFileExistsError for index \(index)")
            } catch {
                let nsError = error as NSError
                XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
                XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
            }
            expectation.fulfill()
        }

        waitForExpectations(timeout: 10.0)

        let preservedData = try Data(contentsOf: fileURL)
        XCTAssertEqual(preservedData, initialData)

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    func testOverwriteFailureCleansStagingAndPreservesOriginal() throws {
        let fileURL = tempDirectory.appendingPathComponent("overwrite-failure.json")
        let initialData = Data("{\"status\": \"original\"}".utf8)
        try FileDurability.writeAtomicDraft(data: initialData, to: fileURL)

        let overwriteData = Data("{\"status\": \"blocked\"}".utf8)

        XCTAssertThrowsError(
            try FileDurability.writeAtomicStaging(data: overwriteData, to: fileURL, overwrite: false)
        ) { error in
            let nsError = error as NSError
            XCTAssertEqual(nsError.domain, NSCocoaErrorDomain)
            XCTAssertEqual(nsError.code, NSFileWriteFileExistsError)
        }

        let currentData = try Data(contentsOf: fileURL)
        XCTAssertEqual(currentData, initialData)

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Staging file was not cleaned up after overwrite failure")
    }
}
