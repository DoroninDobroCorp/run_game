import CoreLocation
import XCTest
@testable import RunGameFounder

final class SessionCoordinatorTests: XCTestCase {
    private var sampleMission: MissionConfig!
    private var appModel: AppModel!
    private var defaults: UserDefaults!
    private var suiteName: String!
    private var tempDir: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        sampleMission = try MissionConfig.loadFromBundle()
        suiteName = "SessionCoordinatorTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
        tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(suiteName, isDirectory: true)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        appModel = MainActor.assumeIsolated {
            AppModel(defaults: defaults, documentsDirectory: tempDir)
        }
    }

    override func tearDownWithError() throws {
        if let suiteName {
            defaults?.removePersistentDomain(forName: suiteName)
        }
        if let tempDir {
            try? FileManager.default.removeItem(at: tempDir)
        }
        sampleMission = nil
        appModel = nil
        defaults = nil
        tempDir = nil
        try super.tearDownWithError()
    }

    @MainActor
    func testCoordinatorLifecycle_RoutesEventsToStateMachineAndUpdatesAppModel() throws {
        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started

        let coordinator = SessionCoordinator(
            mission: sampleMission,
            appModel: appModel,
            audio: fakeAudio,
            recorder: fakeRecorder
        )

        XCTAssertTrue(coordinator.isReady)
        XCTAssertEqual(coordinator.state, .ready)
        XCTAssertEqual(coordinator.currentRunState, .ready)

        let runID = "coord-test-run-1"
        coordinator.send(.requestStart(runID: runID, now: Date()))

        XCTAssertTrue(coordinator.isAcquiringGPS)
        XCTAssertEqual(coordinator.currentRunState, coordinator.state)

        // Verify active journal was saved via AppModel
        let journal = ActiveRunJournal(defaults: defaults)
        if case .attempt(let attempt) = journal.loadJournal() {
            XCTAssertEqual(attempt.runID, runID)
            XCTAssertEqual(attempt.phase, .acquiringGPS)
        } else {
            XCTFail("Journal attempt should exist")
        }

        // Test audio start failure rollback
        coordinator.send(.audioStartFailed(reason: "Test audio failure"))

        XCTAssertTrue(coordinator.isReady)
        XCTAssertEqual(coordinator.currentRunState, .ready)
        if case .none = journal.loadJournal() {
            // Journal cleared
        } else {
            XCTFail("Journal should be cleared after start failure")
        }
        XCTAssertEqual(coordinator.statusMessage, "Test audio failure")
    }

    @MainActor
    func testCoordinatorPublishedStateProperties_ReflectRuntimeChanges() throws {
        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started

        let coordinator = SessionCoordinator(
            mission: sampleMission,
            appModel: appModel,
            audio: fakeAudio,
            recorder: fakeRecorder
        )

        XCTAssertEqual(coordinator.currentRunState, .ready)
        XCTAssertFalse(coordinator.isRecording)
        XCTAssertEqual(coordinator.recordedPointsCount, 0)
        XCTAssertEqual(coordinator.audioElapsedSeconds, 0)
        XCTAssertEqual(coordinator.activeIncidentCount, 0)
        XCTAssertNil(coordinator.statusMessage)

        let runID = "pub-test-run"
        coordinator.send(.requestStart(runID: runID, now: Date()))

        XCTAssertEqual(coordinator.currentRunState, coordinator.state)
        XCTAssertTrue(coordinator.isRecording)

        // Transition to running state
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.audioStarted())

        XCTAssertEqual(coordinator.currentRunState, coordinator.state)
        XCTAssertTrue(coordinator.isRunning)

        fakeAudio.elapsed = 42.0
        fakeAudio.objectWillChangeSubject.send()

        // Wait brief tick for main queue receive
        let expectation = expectation(description: "published updates")
        DispatchQueue.main.async {
            XCTAssertEqual(coordinator.audioElapsedSeconds, 42.0)
            expectation.fulfill()
        }
        wait(for: [expectation], timeout: 1.0)
    }

    @MainActor
    func testFatalAudioErrorInRunningState_TriggersImmediateAbortStopsHardwareEnqueuesDebriefAndSuppressesRecall() throws {
        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started
        let samples = makeSampleTrack()
        let summary = try TrackSummary.make(fileName: "fatal_audio_partial.gpx", samples: samples)
        fakeRecorder.samples = samples
        fakeRecorder.lastSummary = summary

        let coordinator = SessionCoordinator(
            mission: sampleMission,
            appModel: appModel,
            audio: fakeAudio,
            recorder: fakeRecorder
        )

        let runID = "fatal-audio-run"
        coordinator.send(.requestStart(runID: runID, now: Date()))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.audioStarted())

        XCTAssertTrue(coordinator.isRunning)

        // Trigger fatal audio error in running state
        fakeAudio.onFatalError?("Master audio decode failed during playback")

        XCTAssertTrue(coordinator.isAborted)
        XCTAssertEqual(coordinator.currentRunState, coordinator.state)
        XCTAssertFalse(fakeAudio.isPlaying)
        XCTAssertFalse(fakeRecorder.isRecording)

        // Debrief enqueued, recall suppressed
        XCTAssertEqual(appModel.pendingDebriefs.count, 1)
        XCTAssertEqual(appModel.pendingDebriefs.first?.runID, runID)
        XCTAssertTrue(appModel.pendingDebriefs.first?.aborted == true)
        XCTAssertEqual(appModel.pendingRecalls.count, 0)

        // TrackSummary preserved in context
        XCTAssertNotNil(coordinator.currentContext?.track)
        XCTAssertEqual(coordinator.currentContext?.track?.fileName, "fatal_audio_partial.gpx")
        XCTAssertTrue(coordinator.currentContext?.audioIncidents.contains("Master audio decode failed during playback") == true)
    }

    @MainActor
    func testAbortPaths_PreserveTrackSummaryFromLocationRecorder() throws {
        let samples = makeSampleTrack()
        let summary = try TrackSummary.make(fileName: "abort_partial.gpx", samples: samples)

        // 1. Remote stop request path
        let fakeAudio1 = FakeAudioController()
        let fakeRecorder1 = FakeLocationRecorder()
        fakeRecorder1.startResult = .started
        fakeRecorder1.samples = samples
        fakeRecorder1.lastSummary = summary

        let coord1 = SessionCoordinator(mission: sampleMission, appModel: appModel, audio: fakeAudio1, recorder: fakeRecorder1)
        startRunning(coord1)
        fakeAudio1.onStopRequested?()

        XCTAssertTrue(coord1.isAborted)
        XCTAssertEqual(coord1.currentContext?.track?.fileName, "abort_partial.gpx")

        // 2. Interruption path
        let fakeAudio2 = FakeAudioController()
        let fakeRecorder2 = FakeLocationRecorder()
        fakeRecorder2.startResult = .started
        fakeRecorder2.samples = samples
        fakeRecorder2.lastSummary = summary

        let coord2 = SessionCoordinator(mission: sampleMission, appModel: appModel, audio: fakeAudio2, recorder: fakeRecorder2)
        startRunning(coord2)
        fakeAudio2.latestIncidentSubject.send(AudioIncident(
            kind: .interruptionBegan,
            occurredAt: Date(),
            elapsed: 15.0,
            message: "Cellular call incoming"
        ))

        XCTAssertTrue(coord2.isAborted)
        XCTAssertEqual(coord2.currentContext?.track?.fileName, "abort_partial.gpx")

        // 3. Headphone disconnect path
        let fakeAudio3 = FakeAudioController()
        let fakeRecorder3 = FakeLocationRecorder()
        fakeRecorder3.startResult = .started
        fakeRecorder3.samples = samples
        fakeRecorder3.lastSummary = summary

        let coord3 = SessionCoordinator(mission: sampleMission, appModel: appModel, audio: fakeAudio3, recorder: fakeRecorder3)
        startRunning(coord3)
        fakeAudio3.latestIncidentSubject.send(AudioIncident(
            kind: .outputRouteDisconnected,
            occurredAt: Date(),
            elapsed: 30.0,
            message: "Headphones unplugged"
        ))

        XCTAssertTrue(coord3.isAborted)
        XCTAssertEqual(coord3.currentContext?.track?.fileName, "abort_partial.gpx")

        // 4. View dismiss / explicit abortSession path
        let fakeAudio4 = FakeAudioController()
        let fakeRecorder4 = FakeLocationRecorder()
        fakeRecorder4.startResult = .started
        fakeRecorder4.samples = samples
        fakeRecorder4.lastSummary = summary

        let coord4 = SessionCoordinator(mission: sampleMission, appModel: appModel, audio: fakeAudio4, recorder: fakeRecorder4)
        startRunning(coord4)
        coord4.abortSession(reason: "Dismissed view")

        XCTAssertTrue(coord4.isAborted)
        XCTAssertEqual(coord4.currentContext?.track?.fileName, "abort_partial.gpx")
    }

    @MainActor
    func testLocationRecorderStop_HasSingleOwner() throws {
        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started
        let samples = makeSampleTrack()
        fakeRecorder.samples = samples
        fakeRecorder.lastSummary = try TrackSummary.make(fileName: "single_owner.gpx", samples: samples)

        let coordinator = SessionCoordinator(
            mission: sampleMission,
            appModel: appModel,
            audio: fakeAudio,
            recorder: fakeRecorder
        )

        startRunning(coordinator)
        XCTAssertEqual(fakeRecorder.stopCallCount, 0)

        coordinator.abortSession(reason: "Single ownership check")
        XCTAssertTrue(coordinator.isAborted)
        XCTAssertEqual(fakeRecorder.stopCallCount, 1)
    }

    // MARK: - Helpers
    @MainActor
    private func startRunning(_ coordinator: SessionCoordinator) {
        coordinator.send(.requestStart(runID: UUID().uuidString, now: Date()))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.receiveGPSFix(accuracy: 10, distanceToStartMeters: 5))
        coordinator.send(.audioStarted())
    }

    private func makeSampleTrack() -> [TrackSample] {
        let base = Date()
        return [
            TrackSample(latitude: -33.0472, longitude: -71.6127, elevation: 10.0, horizontalAccuracy: 5.0, timestamp: base),
            TrackSample(latitude: -33.0473, longitude: -71.6128, elevation: 11.0, horizontalAccuracy: 5.0, timestamp: base.addingTimeInterval(10))
        ]
    }
}
