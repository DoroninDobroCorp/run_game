import CoreLocation
import XCTest
@testable import RunGameFounder

final class FounderAppTests: XCTestCase {
    func testClockFormatting() {
        XCTAssertEqual(Formatters.clock(0), "00:00")
        XCTAssertEqual(Formatters.clock(365.9), "06:05")
        XCTAssertEqual(Formatters.clock(1800), "30:00")
    }

    func testGPXContainsTrackWithoutPrivateUploadMetadata() throws {
        let samples = [
            TrackSample(
                latitude: -33.046,
                longitude: -71.619,
                elevation: 12,
                horizontalAccuracy: 5,
                timestamp: Date(timeIntervalSince1970: 1_700_000_000)
            ),
            TrackSample(
                latitude: -33.045,
                longitude: -71.618,
                elevation: 14,
                horizontalAccuracy: 4,
                timestamp: Date(timeIntervalSince1970: 1_700_000_010)
            ),
        ]
        let xml = String(decoding: try GPXDocument.data(samples: samples), as: UTF8.self)
        XCTAssertTrue(xml.contains("<trkpt"))
        XCTAssertTrue(xml.contains("Run Game Founder Track"))
        XCTAssertFalse(xml.lowercased().contains("upload"))
        XCTAssertFalse(xml.lowercased().contains("email"))
    }

    func testGPXRejectsEmptyTrack() {
        XCTAssertThrowsError(try GPXDocument.data(samples: []))
    }

    @MainActor
    func testMissionRequiresBothFounderChecks() {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)

        XCTAssertFalse(model.canStartMission)
        model.markHomeAudioCompleted()
        XCTAssertFalse(model.canStartMission)
        model.sidewalksChecked = true
        model.crossingsChecked = true
        model.elevationChecked = true
        model.screenFreeChecked = true
        model.approveRoute()
        XCTAssertTrue(model.canStartMission)
    }

    @MainActor
    func testIncompleteChecklistCannotApproveRoute() {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)

        model.sidewalksChecked = true
        model.approveRoute()
        XCTAssertFalse(model.routeApproved)
    }
}
