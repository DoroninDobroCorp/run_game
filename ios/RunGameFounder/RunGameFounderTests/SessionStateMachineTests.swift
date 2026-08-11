import CoreLocation
import XCTest
@testable import RunGameFounder

@MainActor
final class SessionStateMachineTests: XCTestCase {
    nonisolated(unsafe) private var sampleMission: MissionConfig!
    nonisolated(unsafe) private var defaultPrecommittedDate: Date!

    override func setUpWithError() throws {
        try super.setUpWithError()
        sampleMission = try MissionConfig.loadFromBundle()
        defaultPrecommittedDate = Date().addingTimeInterval(48 * 3600)
    }

    override func tearDownWithError() throws {
        sampleMission = nil
        defaultPrecommittedDate = nil
        try super.tearDownWithError()
    }

    // MARK: - 1. GPS Acquisition Tests
    func testGPSAcquisition_RequiresTwoConsecutiveFixes() {
        var sm = SessionStateMachine()
        XCTAssertTrue(sm.isReady)

        let now = Date()
        let actionsStart = sm.handle(
            event: .requestStart(runID: "test-run-1", now: now),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAcquiringGPS)
        XCTAssertEqual(actionsStart.count, 4)
        XCTAssertEqual(actionsStart[0], .saveJournal(ActiveRunAttempt(
            runID: "test-run-1",
            missionID: sampleMission.missionID,
            bindingID: sampleMission.bindingID,
            audioSHA256: sampleMission.audioSHA256,
            routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
            partialGPXBasename: nil,
            condition: "A",
            phase: .acquiringGPS,
            startedAt: now,
            precommittedNextWorkoutAt: defaultPrecommittedDate,
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )))
        XCTAssertEqual(actionsStart[1], .startGPSRecording(prefix: "\(sampleMission.gpxPrefix)-run-test-run-1"))
        XCTAssertEqual(actionsStart[2], .startFirstFixTimer(seconds: 30))
        XCTAssertEqual(actionsStart[3], .setStatusMessage(nil))

        // Inaccurate fix (>35m) resets count and sets status message
        let actionsInaccurate = sm.handle(
            event: .receiveGPSFix(accuracy: 40.0, distanceToStartMeters: 5.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        XCTAssertTrue(sm.isAcquiringGPS)
        XCTAssertEqual(actionsInaccurate, [.setStatusMessage("GPS accuracy пока ±40 м; ждём значение ≤35 м.")])

        // Far fix (>100m) resets count and sets status message
        let actionsFar = sm.handle(
            event: .receiveGPSFix(accuracy: 10.0, distanceToStartMeters: 120.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        XCTAssertTrue(sm.isAcquiringGPS)
        XCTAssertEqual(actionsFar, [.setStatusMessage("Текущая позиция примерно в 120 м от публичного старта. Подойди к старту; аудио ещё не запущено.")])

        // Fix 1 (valid) -> count becomes 1
        let actionsFix1 = sm.handle(
            event: .receiveGPSFix(accuracy: 10.0, distanceToStartMeters: 5.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        XCTAssertTrue(sm.isAcquiringGPS)
        XCTAssertEqual(actionsFix1, [.setStatusMessage("Получена 1 из 2 последовательных точных GPS-точек у старта…")])

        // Fix 2 (valid) -> count becomes 2, triggers audio playback
        let actionsFix2 = sm.handle(
            event: .receiveGPSFix(accuracy: 12.0, distanceToStartMeters: 8.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        XCTAssertTrue(sm.isAcquiringGPS)
        XCTAssertEqual(actionsFix2, [.cancelFirstFixTimer, .startAudioPlayback])

        // Audio started event transitions state to running
        let audioStartNow = Date()
        let actionsAudioStarted = sm.handle(
            event: .audioStarted(now: audioStartNow),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        XCTAssertTrue(sm.isRunning)
        XCTAssertEqual(actionsAudioStarted.count, 2)
        XCTAssertEqual(actionsAudioStarted[0], .saveJournal(ActiveRunAttempt(
            runID: "test-run-1",
            missionID: sampleMission.missionID,
            bindingID: sampleMission.bindingID,
            audioSHA256: sampleMission.audioSHA256,
            routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
            partialGPXBasename: nil,
            condition: "A",
            phase: .running,
            startedAt: now,
            precommittedNextWorkoutAt: defaultPrecommittedDate,
            pauseCount: 0,
            audioIncidents: [],
            locationIncidents: []
        )))
        XCTAssertEqual(actionsAudioStarted[1], .setStatusMessage(nil))
    }

    func testGPSAcquisition_FirstFixTimeout_RollsBackToReady() {
        var sm = SessionStateMachine()
        _ = sm.handle(
            event: .requestStart(runID: "test-run-timeout", now: Date()),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        let actions = sm.handle(
            event: .gpsFirstFixTimeout,
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isReady)
        XCTAssertEqual(actions, [
            .cancelFirstFixTimer,
            .cancelGPSRecording,
            .stopGPSRecording(completed: false),
            .clearJournal,
            .setStatusMessage("За 30 секунд не получена точная GPS-точка у публичного старта.")
        ])
    }

    func testGPSAcquisition_AudioStartFailed_RollsBackToReady() {
        var sm = SessionStateMachine()
        _ = sm.handle(
            event: .requestStart(runID: "test-run-fail-audio", now: Date()),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        _ = sm.handle(
            event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )
        _ = sm.handle(
            event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        let actions = sm.handle(
            event: .audioStartFailed(reason: "Audio file missing"),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isReady)
        XCTAssertEqual(actions, [
            .cancelFirstFixTimer,
            .cancelGPSRecording,
            .stopGPSRecording(completed: false),
            .clearJournal,
            .setStatusMessage("Audio file missing")
        ])
    }

    // MARK: - 2. Pause & Resume Tests
    func testPauseAndResume_TracksPauseCountCorrectly() {
        var sm = SessionStateMachine()
        let now = Date()
        _ = sm.handle(event: .requestStart(runID: "pause-test", now: now), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: now), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        XCTAssertTrue(sm.isRunning)

        // Pause 1
        let actionsPause1 = sm.handle(event: .pauseRequested, mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        XCTAssertEqual(actionsPause1, [
            .pauseAudioPlayback,
            .saveJournal(ActiveRunAttempt(
                runID: "pause-test",
                missionID: sampleMission.missionID,
                bindingID: sampleMission.bindingID,
                audioSHA256: sampleMission.audioSHA256,
                routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
                partialGPXBasename: nil,
                condition: "A",
                phase: .running,
                startedAt: now,
                precommittedNextWorkoutAt: defaultPrecommittedDate,
                audioElapsedSeconds: 0,
                pauseCount: 1,
                audioIncidents: [],
                locationIncidents: []
            ))
        ])

        // Second pause while already paused should be ignored
        let actionsPause2 = sm.handle(event: .pauseRequested, mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        XCTAssertTrue(actionsPause2.isEmpty)

        // Resume 1
        let actionsResume1 = sm.handle(event: .resumeRequested, mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        XCTAssertEqual(actionsResume1, [
            .startAudioPlayback,
            .saveJournal(ActiveRunAttempt(
                runID: "pause-test",
                missionID: sampleMission.missionID,
                bindingID: sampleMission.bindingID,
                audioSHA256: sampleMission.audioSHA256,
                routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
                partialGPXBasename: nil,
                condition: "A",
                phase: .running,
                startedAt: now,
                precommittedNextWorkoutAt: defaultPrecommittedDate,
                audioElapsedSeconds: 0,
                pauseCount: 1,
                audioIncidents: [],
                locationIncidents: []
            ))
        ])

        // Second resume while playing should be ignored
        let actionsResume2 = sm.handle(event: .resumeRequested, mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        XCTAssertTrue(actionsResume2.isEmpty)

        // Pause 2
        let actionsPause3 = sm.handle(event: .pauseRequested, mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        XCTAssertEqual(actionsPause3, [
            .pauseAudioPlayback,
            .saveJournal(ActiveRunAttempt(
                runID: "pause-test",
                missionID: sampleMission.missionID,
                bindingID: sampleMission.bindingID,
                audioSHA256: sampleMission.audioSHA256,
                routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
                partialGPXBasename: nil,
                condition: "A",
                phase: .running,
                startedAt: now,
                precommittedNextWorkoutAt: defaultPrecommittedDate,
                audioElapsedSeconds: 0,
                pauseCount: 2,
                audioIncidents: [],
                locationIncidents: []
            ))
        ])

        // Verify natural finish preserves pauseCount = 2
        let finishNow = now.addingTimeInterval(sampleMission.durationSeconds)
        let samples = makeTrackSamples(for: sampleMission)
        let summary = try! TrackSummary.make(fileName: "valid.gpx", samples: samples)
        let traversal = WalkthroughEvidence.make(mission: sampleMission, summary: summary, samples: samples)

        _ = sm.handle(
            event: .audioFinishedNaturally(
                summary: summary,
                routeTraversal: traversal,
                audioIncidents: [],
                locationIncidents: [],
                elapsed: sampleMission.durationSeconds,
                now: finishNow
            ),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        if case .completed(let context) = sm.state {
            XCTAssertEqual(context.pauseCount, 2)
            XCTAssertTrue(context.completed)
        } else {
            XCTFail("State should be completed")
        }
    }

    // MARK: - 3. Interruption Tests
    func testAudioInterruption_AbortsRunAndEnqueuesDebrief() {
        var sm = SessionStateMachine()
        let startNow = Date()
        _ = sm.handle(event: .requestStart(runID: "interrupt-test", now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        let actions = sm.handle(
            event: .audioInterrupted(reason: "Incoming phone call", elapsed: 45.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAborted)
        if case .aborted(let context, let reason) = sm.state {
            XCTAssertEqual(reason, "Audio session interrupted: Incoming phone call")
            XCTAssertTrue(context.aborted)
            XCTAssertFalse(context.completed)
            XCTAssertEqual(context.audioElapsedSeconds, 45.0)
            XCTAssertEqual(context.audioIncidents, ["Incoming phone call"])
        } else {
            XCTFail("State should be aborted")
        }

        XCTAssertEqual(actions.count, 6)
        XCTAssertEqual(actions[0], .cancelFirstFixTimer)
        XCTAssertEqual(actions[1], .stopAudioPlayback)
        XCTAssertEqual(actions[2], .stopGPSRecording(completed: false))
        let containsScheduleDebrief = actions.contains { if case .scheduleDebrief = $0 { return true }; return false }
        XCTAssertTrue(containsScheduleDebrief)
        XCTAssertEqual(actions[4], .clearJournal)
        XCTAssertEqual(actions[5], .setStatusMessage("Audio session interrupted: Incoming phone call"))
    }

    func testHeadphoneDisconnect_AbortsRun() {
        var sm = SessionStateMachine()
        let startNow = Date()
        _ = sm.handle(event: .requestStart(runID: "disconnect-test", now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        _ = sm.handle(
            event: .routeDisconnected(elapsed: 120.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAborted)
        if case .aborted(let context, let reason) = sm.state {
            XCTAssertEqual(reason, "Audio session interrupted: Headphones disconnected")
            XCTAssertEqual(context.audioIncidents, ["Headphones disconnected"])
        } else {
            XCTFail("State should be aborted")
        }
    }

    func testRemoteStopRequested_AbortsRun() {
        var sm = SessionStateMachine()
        let startNow = Date()
        _ = sm.handle(event: .requestStart(runID: "remotestop-test", now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        _ = sm.handle(
            event: .remoteStopRequested(elapsed: 300.0),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAborted)
        if case .aborted(let context, let reason) = sm.state {
            XCTAssertEqual(reason, "Remote stop from lock-screen controls")
            XCTAssertEqual(context.audioIncidents, ["Remote stop requested"])
        } else {
            XCTFail("State should be aborted")
        }
    }

    // MARK: - 4. Natural Finish & Recall Tests
    func testNaturalFinish_SuccessfulRun_SchedulesDebriefOnly() throws {
        var sm = SessionStateMachine()
        let startNow = Date()
        _ = sm.handle(event: .requestStart(runID: "natural-test", now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        let finishNow = startNow.addingTimeInterval(sampleMission.durationSeconds)
        let samples = makeTrackSamples(for: sampleMission)
        let summary = try TrackSummary.make(fileName: "natural.gpx", samples: samples)
        let traversal = WalkthroughEvidence.make(mission: sampleMission, summary: summary, samples: samples)

        let actions = sm.handle(
            event: .audioFinishedNaturally(
                summary: summary,
                routeTraversal: traversal,
                audioIncidents: [],
                locationIncidents: [],
                elapsed: sampleMission.durationSeconds,
                now: finishNow
            ),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isCompleted)
        if case .completed(let context) = sm.state {
            XCTAssertTrue(context.completed)
            XCTAssertFalse(context.aborted)
            XCTAssertEqual(context.abortReason, "")
        } else {
            XCTFail("State should be completed")
        }

        XCTAssertTrue(actions.contains(.clearJournal))
        let containsScheduleDebrief = actions.contains { if case .scheduleDebrief = $0 { return true }; return false }
        let containsScheduleRecall = actions.contains { if case .scheduleRecall = $0 { return true }; return false }
        XCTAssertTrue(containsScheduleDebrief)
        XCTAssertFalse(containsScheduleRecall)
    }

    func testNaturalFinish_InsufficientEvidence_AbortsRunWithoutRecall() throws {
        var sm = SessionStateMachine()
        let startNow = Date()
        _ = sm.handle(event: .requestStart(runID: "insufficient-test", now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .receiveGPSFix(accuracy: 10, distanceToStartMeters: 5), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)
        _ = sm.handle(event: .audioStarted(now: startNow), mission: sampleMission, precommittedNextWorkoutAt: defaultPrecommittedDate)

        let finishNow = startNow.addingTimeInterval(sampleMission.durationSeconds)
        // Only 5 samples (insufficient)
        let shortSamples = Array(makeTrackSamples(for: sampleMission).prefix(5))
        let summary = try TrackSummary.make(fileName: "short.gpx", samples: shortSamples)
        let traversal = WalkthroughEvidence.make(mission: sampleMission, summary: summary, samples: shortSamples)

        let actions = sm.handle(
            event: .audioFinishedNaturally(
                summary: summary,
                routeTraversal: traversal,
                audioIncidents: [],
                locationIncidents: [],
                elapsed: sampleMission.durationSeconds,
                now: finishNow
            ),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAborted)
        if case .aborted(let context, _) = sm.state {
            XCTAssertFalse(context.completed)
            XCTAssertTrue(context.aborted)
        } else {
            XCTFail("State should be aborted")
        }

        let containsScheduleDebrief = actions.contains { if case .scheduleDebrief = $0 { return true }; return false }
        let containsScheduleRecall = actions.contains { if case .scheduleRecall = $0 { return true }; return false }
        XCTAssertTrue(containsScheduleDebrief)
        XCTAssertFalse(containsScheduleRecall)
    }

    // MARK: - 5. Crash Recovery Tests
    func testProcessCrashRecovered_RestoresAbortedSession() {
        var sm = SessionStateMachine()
        let crashNow = Date()
        let attempt = ActiveRunAttempt(
            runID: "crash-run-1",
            missionID: sampleMission.missionID,
            bindingID: sampleMission.bindingID,
            audioSHA256: sampleMission.audioSHA256,
            routeWorkoutFingerprint: sampleMission.routeWorkoutFingerprint,
            condition: "A",
            phase: .running,
            startedAt: crashNow.addingTimeInterval(-300),
            precommittedNextWorkoutAt: defaultPrecommittedDate,
            pauseCount: 1,
            audioIncidents: ["Pre-crash incident"],
            locationIncidents: []
        )

        let actions = sm.handle(
            event: .processCrashRecovered(attempt: attempt, endedAt: crashNow),
            mission: sampleMission,
            precommittedNextWorkoutAt: defaultPrecommittedDate
        )

        XCTAssertTrue(sm.isAborted)
        if case .aborted(let context, let reason) = sm.state {
            XCTAssertEqual(context.runID, "crash-run-1")
            XCTAssertTrue(context.aborted)
            XCTAssertFalse(context.completed)
            XCTAssertEqual(reason, "App relaunch recovery: session interrupted in running phase")
            XCTAssertEqual(context.audioIncidents, ["Pre-crash incident", "Interrupted by unexpected process termination"])
        } else {
            XCTFail("State should be aborted")
        }

        XCTAssertEqual(actions.count, 2)
        let containsScheduleDebrief = actions.contains { if case .scheduleDebrief = $0 { return true }; return false }
        XCTAssertTrue(containsScheduleDebrief)
        XCTAssertEqual(actions[1], .clearJournal)
    }

    // MARK: - Helper Methods
    private func makeTrackSamples(for mission: MissionConfig) -> [TrackSample] {
        let base = Date(timeIntervalSince1970: 1_800_000_000)
        var samples: [TrackSample] = []
        let interval: TimeInterval = 75.0 // 24 * 75 = 1800 seconds total duration
        for (pointIndex, point) in mission.routePoints.enumerated() {
            for repetition in 0..<5 {
                let index = pointIndex * 5 + repetition
                samples.append(
                    TrackSample(
                        latitude: point.latitude,
                        longitude: point.longitude,
                        elevation: Double(pointIndex),
                        horizontalAccuracy: 5,
                        timestamp: base.addingTimeInterval(Double(index) * interval)
                    )
                )
            }
        }
        return samples
    }
}
