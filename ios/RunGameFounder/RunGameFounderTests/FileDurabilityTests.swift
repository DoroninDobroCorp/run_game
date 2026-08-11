import XCTest
@testable import RunGameFounder

final class FileDurabilityTests: XCTestCase {
    private var tempDirectory: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        FileDurability.injectedFailure = .none
        tempDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent("FileDurabilityTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tempDirectory, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        FileDurability.injectedFailure = .none
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

        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let queueKeyBytes: [UInt8] = [102, 111, 117, 110, 100, 101, 114, 46, 118, 50, 46, 112, 101, 110, 100, 105, 110, 103, 68, 101, 98, 114, 105, 101, 102, 115]
        let debriefKey = String(bytes: queueKeyBytes, encoding: .utf8)!
        defaults.set(Data("corrupted json data".utf8), forKey: debriefKey)

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)

        XCTAssertTrue(model.queueCorrupted)
        XCTAssertTrue(model.evidenceCaptureLocked)

        // Also verify corrupted file on disk sets queueCorrupted
        let docDir2 = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir2, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir2) }

        let fileURL = docDir2.appendingPathComponent("pending_debriefs.json")
        try Data("corrupted json data".utf8).write(to: fileURL)

        let model2 = AppModel(defaults: defaults, documentsDirectory: docDir2)
        XCTAssertTrue(model2.queueCorrupted)
        XCTAssertTrue(model2.evidenceCaptureLocked)
    }

    @MainActor
    func testConcurrentAtomicWrites() async throws {
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

        await fulfillment(of: [expectation], timeout: 10.0)

        let files = try FileManager.default.contentsOfDirectory(atPath: targetDir.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    @MainActor
    func testConcurrentOverwriteProtection() async throws {
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

        await fulfillment(of: [expectation], timeout: 10.0)

        let preservedData = try Data(contentsOf: fileURL)
        XCTAssertEqual(preservedData, initialData)

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Leftover staging files found: \(tmpFiles)")
    }

    @MainActor
    func test20ConcurrentWritersToUncreatedDestinationURL() async throws {
        let fileURL = tempDirectory.appendingPathComponent("concurrent-uncreated-target.json")
        let iterations = 20
        let expectation = expectation(description: "20 concurrent writers to uncreated destination complete")
        expectation.expectedFulfillmentCount = iterations

        nonisolated(unsafe) var successCount = 0
        nonisolated(unsafe) var fileExistsRejections = 0
        nonisolated(unsafe) var unexpectedErrors: [String] = []
        nonisolated(unsafe) var winningPayload: Data?
        let lock = NSLock()

        DispatchQueue.concurrentPerform(iterations: iterations) { index in
            let payload = Data("{\"writer_index\": \(index)}".utf8)
            do {
                try FileDurability.writeFinalEvidence(data: payload, to: fileURL)
                lock.withLock {
                    successCount += 1
                    winningPayload = payload
                }
            } catch {
                let nsError = error as NSError
                if nsError.domain == NSCocoaErrorDomain && nsError.code == NSFileWriteFileExistsError {
                    lock.withLock {
                        fileExistsRejections += 1
                    }
                } else {
                    lock.withLock {
                        unexpectedErrors.append("Index \(index) failed with unexpected error: \(error)")
                    }
                }
            }
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 10.0)

        XCTAssertEqual(unexpectedErrors, [], "No unexpected errors should occur")
        XCTAssertEqual(successCount, 1, "Exactly 1 writer should succeed")
        XCTAssertEqual(fileExistsRejections, 19, "Exactly 19 writers should receive file-exists rejection")

        XCTAssertTrue(FileManager.default.fileExists(atPath: fileURL.path), "Destination file must exist")
        let readData = try Data(contentsOf: fileURL)
        XCTAssertEqual(readData, winningPayload, "Destination file content must match winning payload")
        XCTAssertTrue(FileDurability.isExcludedFromBackup(url: fileURL), "Destination file must be excluded from backup")

        let files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        let tmpFiles = files.filter { $0.hasPrefix(".tmp.") }
        XCTAssertTrue(tmpFiles.isEmpty, "Zero temporary staging files should remain, found: \(tmpFiles)")
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

    func testFilesystemFailureInjectionCleanUp() throws {
        let fileURL = tempDirectory.appendingPathComponent("failure-injection.json")
        let testData = Data("{\"status\": \"failure_test\"}".utf8)

        // 1. Fail staging write
        FileDurability.injectedFailure = .failStagingWrite
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        var files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on staging write failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 2. Fail staging sync
        FileDurability.injectedFailure = .failStagingSync
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on staging sync failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 3. Fail publication
        FileDurability.injectedFailure = .failPublication
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        files = try FileManager.default.contentsOfDirectory(atPath: tempDirectory.path)
        XCTAssertTrue(files.filter { $0.hasPrefix(".tmp.") }.isEmpty, "Staging file must be cleaned up on publication failure")
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))

        // 4. Fail parent sync
        FileDurability.injectedFailure = .failParentSync
        XCTAssertThrowsError(try FileDurability.writeAtomicDraft(data: testData, to: fileURL))
        FileDurability.injectedFailure = .none
    }
}
