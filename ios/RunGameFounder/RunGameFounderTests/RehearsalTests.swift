import XCTest
@testable import RunGameFounder

@MainActor
final class RehearsalTests: XCTestCase {
    func testFullThirtyMinuteRehearsalUsesSessionEngineAndVisitsLoop() throws {
        let rehearsal = Rehearsal(mission: try OfflineRouteTests.missionWithGeometry())
        rehearsal.play()
        XCTAssertTrue(rehearsal.stateMachine.isRunning)
        rehearsal.advance(by: 1800)
        let report = try XCTUnwrap(rehearsal.report)
        XCTAssertTrue(report.sessionCompleted)
        XCTAssertTrue(report.simulated)
        XCTAssertFalse(report.fieldEvidence)
        XCTAssertFalse(report.audioPlaybackVerified)
        XCTAssertEqual(report.durationSeconds, 1800)
        XCTAssertEqual(report.sampleCount, 901)
        XCTAssertEqual(report.visitedWaypoints, 5)
        XCTAssertEqual(report.intervalsCompleted, 8)
        XCTAssertFalse(rehearsal.isPlaying)
    }

    func testPauseResumeResetAndInvalidTicks() throws {
        let rehearsal = Rehearsal(mission: try OfflineRouteTests.missionWithGeometry())
        rehearsal.play()
        rehearsal.advance(by: 100)
        rehearsal.pause()
        rehearsal.advance(by: 100)
        XCTAssertEqual(rehearsal.elapsed, 100)
        rehearsal.play()
        rehearsal.advance(by: .nan)
        rehearsal.advance(by: -10)
        rehearsal.advance(by: .infinity)
        XCTAssertEqual(rehearsal.elapsed, 100)
        rehearsal.advance(by: 1700)
        XCTAssertTrue(try XCTUnwrap(rehearsal.report).sessionCompleted)
        rehearsal.reset()
        XCTAssertNil(rehearsal.report)
        XCTAssertEqual(rehearsal.elapsed, 0)
        XCTAssertTrue(rehearsal.stateMachine.isReady)
    }

    func testSavedSimulationContainsNoCoordinatesOrResearchQueues() throws {
        let rehearsal = Rehearsal(mission: try OfflineRouteTests.missionWithGeometry())
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        rehearsal.play()
        rehearsal.advance(by: 1800)
        rehearsal.saveReport(directory: directory)
        let url = try XCTUnwrap(rehearsal.reportURL)
        let data = try Data(contentsOf: url)
        let text = String(decoding: data, as: UTF8.self)
        XCTAssertFalse(text.contains("latitude"))
        XCTAssertFalse(text.contains("longitude"))
        XCTAssertFalse(text.contains("participantID"))
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path).count, 1)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["simulated"] as? Bool, true)
        XCTAssertEqual(json["fieldEvidence"] as? Bool, false)
        rehearsal.saveReport(directory: directory)
        XCTAssertEqual(rehearsal.reportURL, url)
    }

    func testNoGeometryDoesNotStartAndRunningMovesFasterThanWalking() throws {
        var mission = try OfflineRouteTests.missionWithGeometry()
        let walking = Rehearsal.routeProgress(at: 120, mission: mission) - Rehearsal.routeProgress(at: 60, mission: mission)
        let running = Rehearsal.routeProgress(at: 360, mission: mission) - Rehearsal.routeProgress(at: 300, mission: mission)
        XCTAssertGreaterThan(running, walking)
        mission.offlineRoute = nil
        let rehearsal = Rehearsal(mission: mission)
        rehearsal.play()
        XCTAssertFalse(rehearsal.isPlaying)
        XCTAssertNil(rehearsal.report)
    }
}
