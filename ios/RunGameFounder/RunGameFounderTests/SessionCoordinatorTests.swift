import CoreLocation
import XCTest
@testable import RunGameFounder

final class SessionCoordinatorTests: XCTestCase {
    private var sampleMission: MissionConfig!
    private var appModel: AppModel!
    private var defaults: UserDefaults!
    private var suiteName: String!

    override func setUpWithError() throws {
        try super.setUpWithError()
        sampleMission = try MissionConfig.loadFromBundle()
        suiteName = "SessionCoordinatorTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)!
        appModel = MainActor.assumeIsolated {
            AppModel(defaults: defaults)
        }
    }

    override func tearDownWithError() throws {
        if let suiteName {
            defaults?.removePersistentDomain(forName: suiteName)
        }
        sampleMission = nil
        appModel = nil
        defaults = nil
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

        let runID = "coord-test-run-1"
        coordinator.send(.requestStart(runID: runID, now: Date()))

        XCTAssertTrue(coordinator.isAcquiringGPS)

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
        if case .none = journal.loadJournal() {
            // Journal cleared
        } else {
            XCTFail("Journal should be cleared after start failure")
        }
        XCTAssertEqual(coordinator.statusMessage, "Test audio failure")
    }

    @MainActor
    func testCoordinatorAbort_EnqueuesDebriefAndClearsJournal() throws {
        let fakeAudio = FakeAudioController()
        let fakeRecorder = FakeLocationRecorder()
        fakeRecorder.startResult = .started

        let coordinator = SessionCoordinator(
            mission: sampleMission,
            appModel: appModel,
            audio: fakeAudio,
            recorder: fakeRecorder
        )

        let runID = "coord-test-abort"
        coordinator.send(.requestStart(runID: runID, now: Date()))

        XCTAssertTrue(coordinator.isAcquiringGPS)

        coordinator.send(.userAborted(
            reason: "User tapped abort",
            summary: nil,
            routeTraversal: nil,
            audioIncidents: [],
            locationIncidents: [],
            elapsed: 30.0
        ))

        XCTAssertTrue(coordinator.isAborted)
        XCTAssertEqual(appModel.pendingDebriefs.count, 1)
        XCTAssertEqual(appModel.pendingDebriefs.first?.runID, runID)
        XCTAssertTrue(appModel.pendingDebriefs.first?.aborted == true)
        XCTAssertEqual(appModel.pendingRecalls.count, 0)

        let journal = ActiveRunJournal(defaults: defaults)
        if case .none = journal.loadJournal() {} else {
            XCTFail("Journal should be cleared after abort")
        }
    }
}
