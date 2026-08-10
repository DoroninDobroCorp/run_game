import Foundation
import XCTest
@testable import RunGameFounder

final class AppModelLockTests: XCTestCase {
    @MainActor
    func testEvidenceCaptureLocked_WhenPendingDebriefsNonEmpty() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        
        XCTAssertFalse(model.evidenceCaptureLocked)
        
        let endedAt = Date()
        let context = RunSessionContext(
            runID: "test-run-1",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-100),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(86400),
            completed: false,
            aborted: true,
            abortReason: "Aborted for test",
            audioElapsedSeconds: 100,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )
        
        model.scheduleDebrief(for: context)
        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertFalse(model.canBeginMission)
        
        model.completeDebrief(runID: context.runID)
        XCTAssertFalse(model.evidenceCaptureLocked)
    }

    @MainActor
    func testEvidenceCaptureLocked_WhenPendingRecallsNonEmpty() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        
        XCTAssertFalse(model.evidenceCaptureLocked)
        
        let endedAt = Date()
        let context = RunSessionContext(
            runID: "test-run-2",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-1800),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(86400),
            completed: true,
            aborted: false,
            abortReason: "",
            audioElapsedSeconds: 1800,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )
        
        model.scheduleRecall(for: context)
        XCTAssertTrue(model.evidenceCaptureLocked)
        XCTAssertFalse(model.canBeginMission)
        
        model.completeRecall(runID: context.runID)
        XCTAssertFalse(model.evidenceCaptureLocked)
    }

    @MainActor
    func testAbortedRunDoesNotEnqueuePendingRecall() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        
        let endedAt = Date()
        let abortedContext = RunSessionContext(
            runID: "test-aborted-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-100),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(86400),
            completed: false,
            aborted: true,
            abortReason: "Aborted test",
            audioElapsedSeconds: 100,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )
        
        model.scheduleDebrief(for: abortedContext)
        XCTAssertEqual(model.pendingDebriefs.count, 1)
        XCTAssertTrue(model.pendingRecalls.isEmpty)
    }

    @MainActor
    func testDebriefRecordSchema03AndUnclampedRecordingDelay() throws {
        let endedAt = Date(timeIntervalSince1970: 1_000_000)
        let recordedAt = endedAt.addingTimeInterval(-5.25)
        
        let record = DebriefRecord(
            schemaVersion: "0.3",
            recordStatus: "immediate_complete",
            runID: "test-run-schema-03",
            bindingID: "binding-123",
            missionID: "m01",
            condition: "A",
            participantRole: "founder",
            startedAtLocal: endedAt.addingTimeInterval(-1800),
            endedAtLocal: endedAt,
            recordedAtLocal: recordedAt,
            recordingDelaySeconds: recordedAt.timeIntervalSince(endedAt),
            precommittedNextWorkoutAtLocal: endedAt.addingTimeInterval(86400),
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            track: nil,
            routeTraversalEvidence: nil,
            safety: SafetyEvidence(routeManuallyChecked: true, abort: false, abortReason: "", neededScreenWhileMoving: false, navConflicts: []),
            runtime: RuntimeEvidence(completed: true, geoSlotsReached: [], geoFallbacksUsed: [], missedOrLateCues: [], operatorImprovisationUsed: false, audioIncidents: [], additionalAudioNotes: "", offRouteIncidents: [], pauseCount: 0, locationIncidents: []),
            immediateDebriefBeforeEdits: ImmediateDebriefEvidence(missionGoalInOneSentence: "Goal", momentCompanionBecameImportant: "Moment", unaidedMemorableScene: "Scene", attentionDropMoment: "Drop", whatPhysicalMovementChanged: "Movement", desireForM02_1To7: 5, placeNecessity1To7: 5, predictedNextTwist: "Twist", nextWorkoutStillScheduled: true),
            recallAfter24h: RecallAfter24HoursEvidence(pending: true, instructions: "Instr"),
            confounds: ConfoundEvidence(unfamiliarCityNovelty: "", fatigue: "", noise: "", weather: "", routeQuality: "", audioQuality: "", elevationOrStairs: ""),
            device: DeviceEvidence(model: "iPhone", systemName: "iOS", systemVersion: "18.5", headphones: "AirPods", lockScreenUsed: true, lockScreenAnswerRecorded: true),
            evidenceLimits: []
        )
        
        XCTAssertEqual(record.schemaVersion, "0.3")
        XCTAssertEqual(record.recordingDelaySeconds, -5.25, accuracy: 0.001)
        
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(record)
        
        let jsonDict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(jsonDict["schema_version"] as? String, "0.3")
        XCTAssertEqual(jsonDict["recording_delay_seconds"] as? Double, -5.25)
    }
}
