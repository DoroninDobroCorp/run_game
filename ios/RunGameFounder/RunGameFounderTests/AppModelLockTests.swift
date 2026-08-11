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
    func testScheduleRecallGuardsAgainstAbortedContext() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)

        let endedAt = Date()
        let abortedContext = RunSessionContext(
            runID: "test-aborted-run-recall",
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

        model.scheduleRecall(for: abortedContext)
        XCTAssertTrue(model.pendingRecalls.isEmpty)
    }

    @MainActor
    func testLocalEvidenceURLsExcludesDraftsAndPartialGPX() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }

        try Data("partial".utf8).write(to: directory.appendingPathComponent("run.partial.gpx"))
        try Data("draft".utf8).write(to: directory.appendingPathComponent("m01-run1-draft.json"))
        try Data("immediate".utf8).write(to: directory.appendingPathComponent("m01-run1-immediate.json"))

        let model = AppModel(defaults: defaults, documentsDirectory: directory)
        XCTAssertEqual(model.localEvidenceURLs.map(\.lastPathComponent), ["m01-run1-immediate.json"])
        XCTAssertEqual(model.recoveredTrackURLs.map(\.lastPathComponent), ["run.partial.gpx"])
    }

    @MainActor
    func testLocalEvidenceIndexFiltering_SuppressesImmediateAndDraftJSONDuringPendingRecall() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }

        try Data("partial".utf8).write(to: directory.appendingPathComponent("run.partial.gpx"))
        try Data("walkthrough".utf8).write(to: directory.appendingPathComponent("m01-walkthrough.gpx"))
        try Data("draft".utf8).write(to: directory.appendingPathComponent("m01-run1-draft.json"))
        try Data("immediate".utf8).write(to: directory.appendingPathComponent("m01-run1-immediate.json"))

        let model = AppModel(defaults: defaults, documentsDirectory: directory)
        let mission = try XCTUnwrap(model.mission)

        // Before recall pending: localEvidenceURLs contains immediate.json and walkthrough.gpx
        XCTAssertEqual(model.localEvidenceURLs.map(\.lastPathComponent), ["m01-run1-immediate.json", "m01-walkthrough.gpx"])
        XCTAssertEqual(model.recoveredTrackURLs.map(\.lastPathComponent), ["run.partial.gpx"])

        let endedAt = Date()
        let context = RunSessionContext(
            runID: "m01-run1",
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

        // Schedule recall -> recall becomes pending
        model.scheduleRecall(for: context)
        XCTAssertTrue(model.evidenceCaptureLocked)

        // During pending recall: localEvidenceURLs suppresses immediate & draft JSON, exposing only raw GPX files
        XCTAssertEqual(model.localEvidenceURLs.map(\.lastPathComponent), ["m01-walkthrough.gpx"])
        XCTAssertEqual(model.recoveredTrackURLs.map(\.lastPathComponent), ["run.partial.gpx"])

        // Complete recall -> localEvidenceURLs shows immediate.json again
        model.completeRecall(runID: context.runID)
        XCTAssertFalse(model.evidenceCaptureLocked)
        XCTAssertEqual(model.localEvidenceURLs.map(\.lastPathComponent), ["m01-run1-immediate.json", "m01-walkthrough.gpx"])
    }

    @MainActor
    func testSinglePointRecallScheduling_OnlyScheduledOnImmediateDebriefSave() throws {
        let suiteName = "AppModelLockTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)

        let endedAt = Date()
        let context = RunSessionContext(
            runID: "test-run-single-point",
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

        // 1. Session finishes -> only scheduleDebrief is called
        model.scheduleDebrief(for: context)
        XCTAssertEqual(model.pendingDebriefs.count, 1)
        XCTAssertTrue(model.pendingRecalls.isEmpty)
        XCTAssertTrue(model.evidenceCaptureLocked)

        // 2. Immediate debrief saved durably -> scheduleRecall is called and debrief completed
        model.scheduleRecall(for: context)
        model.completeDebrief(runID: context.runID)
        XCTAssertTrue(model.pendingDebriefs.isEmpty)
        XCTAssertEqual(model.pendingRecalls.count, 1)
        XCTAssertTrue(model.evidenceCaptureLocked)
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

    @MainActor
    func testParticipantId_LocalDeviceStorageAndPropagation() throws {
        let suiteName = "AppModelLockTests.ParticipantId.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        // 1. Initial creation generates and persists participantId
        let customId = "participant_founder_test_123"
        let model1 = AppModel(defaults: defaults, participantId: customId)
        XCTAssertEqual(model1.participantId, customId)
        XCTAssertEqual(defaults.string(forKey: AppModel.participantIdKey), customId)

        // 2. Subsequent AppModel load restores existing participantId
        let model2 = AppModel(defaults: defaults)
        XCTAssertEqual(model2.participantId, customId)

        // 3. Propagation across RunSessionContext -> DebriefRecord & PendingRecall -> RecallCompletionRecord
        let endedAt = Date()
        let context = RunSessionContext(
            participantID: model2.participantId,
            runID: "test-run-participant-propagation",
            missionID: "m01",
            bindingID: "binding-valparaiso",
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
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

        XCTAssertEqual(context.participantID, customId)

        let pendingRecall = PendingRecall.make(context: context)
        XCTAssertEqual(pendingRecall.participantID, customId)

        let debriefRecord = DebriefRecord(
            schemaVersion: "0.3",
            recordStatus: "immediate_complete",
            participantID: context.participantID,
            runID: context.runID,
            bindingID: context.bindingID,
            missionID: context.missionID,
            condition: context.condition,
            participantRole: "founder",
            startedAtLocal: context.startedAt,
            endedAtLocal: context.endedAt,
            recordedAtLocal: endedAt.addingTimeInterval(60),
            recordingDelaySeconds: 60,
            precommittedNextWorkoutAtLocal: context.precommittedNextWorkoutAt,
            audioSHA256: context.audioSHA256,
            routeWorkoutFingerprint: context.routeWorkoutFingerprint,
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

        XCTAssertEqual(debriefRecord.participantID, customId)

        let recallRecord = RecallCompletionRecord(
            schemaVersion: "0.2",
            recordStatus: "recall_24h_complete",
            participantID: pendingRecall.participantID,
            runID: pendingRecall.runID,
            bindingID: pendingRecall.bindingID,
            missionID: pendingRecall.missionID,
            condition: pendingRecall.condition,
            audioSHA256: pendingRecall.audioSHA256,
            routeWorkoutFingerprint: pendingRecall.routeWorkoutFingerprint,
            runEndedAtLocal: pendingRecall.runEndedAt,
            dueAtLocal: pendingRecall.dueAt,
            completedAtLocal: pendingRecall.dueAt.addingTimeInterval(1800),
            unaidedStoryRecall: "Story",
            unaidedPlaceRecall: ["Place 1"],
            desireForM02_1To7: 6,
            evidenceLimits: []
        )

        XCTAssertEqual(recallRecord.participantID, customId)
        XCTAssertEqual(debriefRecord.participantID, recallRecord.participantID)

        // Verify JSON encoding produces snake_case participant_id
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601

        let immData = try encoder.encode(debriefRecord)
        let immDict = try JSONSerialization.jsonObject(with: immData) as! [String: Any]
        XCTAssertEqual(immDict["participant_id"] as? String, customId)

        let recData = try encoder.encode(recallRecord)
        let recDict = try JSONSerialization.jsonObject(with: recData) as! [String: Any]
        XCTAssertEqual(recDict["participant_id"] as? String, customId)
    }

    @MainActor
    func testSwiftStructJSONPayloadsPassPythonValidatorPairChecking() throws {
        let participantId = "participant_founder_parity_001"
        let endedAt = Date(timeIntervalSince1970: 1_770_000_000)
        let startedAt = endedAt.addingTimeInterval(-1800)
        let recordedAt = endedAt.addingTimeInterval(300)
        let precommittedAt = endedAt.addingTimeInterval(86400)

        let trackSummary = TrackSummary(
            fileName: "run-parity.gpx",
            fileSHA256: String(repeating: "c", count: 64),
            sampleCount: 50,
            startedAt: startedAt,
            endedAt: endedAt,
            durationSeconds: 1800,
            distanceMeters: 2500,
            meanHorizontalAccuracyMeters: 5,
            maximumSampleGapSeconds: 10
        )

        let debriefRecord = DebriefRecord(
            schemaVersion: "0.3",
            recordStatus: "immediate_complete",
            participantID: participantId,
            runID: "run-parity-001",
            bindingID: "valparaiso_central",
            missionID: "m01",
            condition: "A",
            participantRole: "founder",
            startedAtLocal: startedAt,
            endedAtLocal: endedAt,
            recordedAtLocal: recordedAt,
            recordingDelaySeconds: 300,
            precommittedNextWorkoutAtLocal: precommittedAt,
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            track: trackSummary,
            routeTraversalEvidence: nil,
            safety: SafetyEvidence(routeManuallyChecked: true, abort: false, abortReason: "", neededScreenWhileMoving: false, navConflicts: []),
            runtime: RuntimeEvidence(completed: true, geoSlotsReached: ["slot1"], geoFallbacksUsed: [], missedOrLateCues: [], operatorImprovisationUsed: false, audioIncidents: [], additionalAudioNotes: "", offRouteIncidents: [], pauseCount: 0, locationIncidents: []),
            immediateDebriefBeforeEdits: ImmediateDebriefEvidence(missionGoalInOneSentence: "Goal sentence.", momentCompanionBecameImportant: "Moment.", unaidedMemorableScene: "Scene.", attentionDropMoment: "None.", whatPhysicalMovementChanged: "Pace.", desireForM02_1To7: 6, placeNecessity1To7: 7, predictedNextTwist: "Twist.", nextWorkoutStillScheduled: true),
            recallAfter24h: RecallAfter24HoursEvidence(pending: true, instructions: "Recall in 24h"),
            confounds: ConfoundEvidence(unfamiliarCityNovelty: "", fatigue: "", noise: "", weather: "", routeQuality: "", audioQuality: "", elevationOrStairs: ""),
            device: DeviceEvidence(model: "iPhone 16 Pro", systemName: "iOS", systemVersion: "18.5", headphones: "AirPods Pro", lockScreenUsed: true, lockScreenAnswerRecorded: true),
            evidenceLimits: ["Founder test"]
        )

        let dueAt = endedAt.addingTimeInterval(86400)
        let completedAt = dueAt.addingTimeInterval(1800)

        let recallRecord = RecallCompletionRecord(
            schemaVersion: "0.2",
            recordStatus: "recall_24h_complete",
            participantID: participantId,
            runID: "run-parity-001",
            bindingID: "valparaiso_central",
            missionID: "m01",
            condition: "A",
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            runEndedAtLocal: endedAt,
            dueAtLocal: dueAt,
            completedAtLocal: completedAt,
            unaidedStoryRecall: "Story recall.",
            unaidedPlaceRecall: ["Plaza Sotomayor"],
            desireForM02_1To7: 6,
            evidenceLimits: ["Recall completed."]
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase

        let immData = try encoder.encode(debriefRecord)
        let recData = try encoder.encode(recallRecord)

        let immDict = try JSONSerialization.jsonObject(with: immData) as! [String: Any]
        let recDict = try JSONSerialization.jsonObject(with: recData) as! [String: Any]

        // Verify top-level parity fields encoded directly by Swift structs
        XCTAssertEqual(immDict["schema_version"] as? String, "0.3")
        XCTAssertEqual(recDict["schema_version"] as? String, "0.2")

        XCTAssertEqual(immDict["record_status"] as? String, "immediate_complete")
        XCTAssertEqual(recDict["record_status"] as? String, "recall_24h_complete")

        XCTAssertEqual(immDict["participant_id"] as? String, participantId)
        XCTAssertEqual(recDict["participant_id"] as? String, participantId)
        XCTAssertEqual(immDict["participant_id"] as? String, recDict["participant_id"] as? String)

        XCTAssertEqual(immDict["run_id"] as? String, recDict["run_id"] as? String)
        XCTAssertEqual(immDict["binding_id"] as? String, recDict["binding_id"] as? String)
        XCTAssertEqual(immDict["mission_id"] as? String, recDict["mission_id"] as? String)
        XCTAssertEqual(immDict["condition"] as? String, recDict["condition"] as? String)
        XCTAssertEqual(immDict["audio_sha256"] as? String, recDict["audio_sha256"] as? String)
        XCTAssertEqual(immDict["route_workout_fingerprint"] as? String, recDict["route_workout_fingerprint"] as? String)
    }
}
