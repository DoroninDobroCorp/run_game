import Foundation
import XCTest
@testable import RunGameFounder

final class ActiveRunJournalTests: XCTestCase {
    @MainActor
    func testJournalPersistsMetadataWithoutCoordinates() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        
        let journal = ActiveRunJournal(defaults: defaults)
        XCTAssertNil(journal.currentAttempt)
        
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "test-run-123",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            phase: .running,
            startedAt: Date(),
            pauseCount: 1,
            audioIncidents: ["Audio paused"],
            locationIncidents: []
        )
        
        journal.save(attempt)
        XCTAssertNotNil(journal.currentAttempt)
        
        // Inspect raw UserDefaults data to ensure NO coordinate keys exist
        let data = try XCTUnwrap(defaults.data(forKey: ActiveRunJournal.journalKey))
        let jsonDict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        
        XCTAssertEqual(jsonDict["run_id"] as? String, "test-run-123")
        XCTAssertEqual(jsonDict["schema_version"] as? String, "0.1")
        XCTAssertNil(jsonDict["latitude"])
        XCTAssertNil(jsonDict["longitude"])
        XCTAssertNil(jsonDict["coordinates"])
        XCTAssertNil(jsonDict["track_points"])
        XCTAssertNil(jsonDict["samples"])
        XCTAssertNil(jsonDict["gpx"])
    }

    @MainActor
    func testRelaunchWithActiveJournalRestoresAbortedContextAndLocksEvidence() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        
        let initialModel = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(initialModel.mission)
        
        // 1. Create an active run attempt in defaults prior to AppModel init
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "crashed-run-789",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            phase: .running,
            startedAt: Date().addingTimeInterval(-300),
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let attemptData = try encoder.encode(attempt)
        defaults.set(attemptData, forKey: ActiveRunJournal.journalKey)
        
        // 2. Initialize AppModel (simulating app relaunch)
        let model = AppModel(defaults: defaults)
        
        // 3. Verify evidence lock and restored aborted context
        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertEqual(model.pendingDebriefs.count, 1)
        
        let restored = try XCTUnwrap(model.pendingDebriefs.first)
        XCTAssertEqual(restored.runID, "crashed-run-789")
        XCTAssertTrue(restored.aborted)
        XCTAssertFalse(restored.completed)
        XCTAssertTrue(restored.abortReason.contains("App relaunch recovery"))
        
        // 4. Verify active journal key in defaults was cleared
        XCTAssertNil(defaults.data(forKey: ActiveRunJournal.journalKey))
    }

    @MainActor
    func testCorruptedJournalFailsClosed() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        
        // Set invalid data in active journal key
        defaults.set(Data("corrupted json data".utf8), forKey: ActiveRunJournal.journalKey)
        
        let model = AppModel(defaults: defaults)
        
        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertTrue(model.journalCorrupted)
        XCTAssertNotNil(model.journalErrorBanner)
    }

    @MainActor
    func testJournalClearedOnNormalFinishOrAbort() throws {
        let suiteName = "ActiveRunJournalTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        
        let journal = ActiveRunJournal(defaults: defaults)
        let attempt = ActiveRunAttempt(
            schemaVersion: "0.1",
            runID: "normal-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            phase: .running,
            startedAt: Date(),
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )
        journal.save(attempt)
        XCTAssertNotNil(journal.currentAttempt)
        
        journal.clear()
        XCTAssertNil(journal.currentAttempt)
        XCTAssertNil(defaults.data(forKey: ActiveRunJournal.journalKey))
    }
}
