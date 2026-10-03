import XCTest
@testable import RunGameFounder

@MainActor
final class OfflineRouteTests: XCTestCase {
    static func missionWithGeometry() throws -> MissionConfig {
        var mission = try MissionConfig.loadFromBundle()
        var coordinates: [RouteCoordinate] = []
        var indices = [0]
        for (a, b) in zip(mission.routePoints, mission.routePoints.dropFirst()) {
            for step in 0..<10 {
                let t = Double(step) / 10
                coordinates.append(RouteCoordinate(latitude: a.latitude + (b.latitude - a.latitude) * t,
                                                   longitude: a.longitude + (b.longitude - a.longitude) * t))
            }
            indices.append(coordinates.count)
        }
        let last = try XCTUnwrap(mission.routePoints.last)
        coordinates.append(RouteCoordinate(latitude: last.latitude, longitude: last.longitude))
        let route = OfflineRoute(coordinates: coordinates, waypointIndices: indices,
            source: "Synthetic test", attribution: "Synthetic", note: "Not a field route")
        mission.offlineRoute = route
        mission.offlineRouteSHA256 = try BundleIntegrity.canonicalSHA256(of: route)
        return mission
    }

    func testOfflineRouteValidatesAndLoadsWithoutDirectionsRequest() async throws {
        let mission = try Self.missionWithGeometry()
        XCTAssertNoThrow(try mission.validate())
        let planner = RoutePlanner()
        await planner.load(points: mission.routePoints, offlineRoute: mission.offlineRoute)
        XCTAssertTrue(planner.isComplete)
        XCTAssertTrue(planner.usesOfflineGeometry)
        XCTAssertFalse(planner.isLoading)
        XCTAssertNil(planner.errorMessage)
        XCTAssertEqual(planner.completedLegs, 4)
        XCTAssertGreaterThan(planner.distanceMeters, 200)
    }

    func testGeometryHashAndFingerprintRejectChangedRoute() throws {
        var mission = try Self.missionWithGeometry()
        let fingerprint = mission.routeWorkoutFingerprint
        let route = try XCTUnwrap(mission.offlineRoute)
        var points = route.coordinates
        points[1] = RouteCoordinate(latitude: points[1].latitude + 0.00005, longitude: points[1].longitude)
        mission.offlineRoute = OfflineRoute(coordinates: points, waypointIndices: route.waypointIndices,
            source: route.source, attribution: route.attribution, note: route.note)
        XCTAssertThrowsError(try mission.validate())
        XCTAssertNotEqual(fingerprint, mission.routeWorkoutFingerprint)
    }

    func testCancelledOnlinePreviewStopsLoadingWithoutRequestOrError() async throws {
        let mission = try Self.missionWithGeometry()
        let planner = RoutePlanner()
        let request = Task { await planner.load(points: mission.routePoints) }
        request.cancel()
        await request.value
        XCTAssertFalse(planner.isLoading)
        XCTAssertNil(planner.errorMessage)
        XCTAssertFalse(planner.isComplete)
        XCTAssertTrue(planner.polylines.isEmpty)
    }

    func testWaypointReorderingAndDetachedHashAreRejected() throws {
        var mission = try Self.missionWithGeometry()
        let route = try XCTUnwrap(mission.offlineRoute)
        let invalid = OfflineRoute(coordinates: route.coordinates, waypointIndices: [0, 20, 10, 30, 40],
            source: route.source, attribution: route.attribution, note: route.note)
        XCTAssertThrowsError(try invalid.validate(waypoints: mission.routePoints))
        mission.offlineRoute = nil
        XCTAssertThrowsError(try mission.validate())
    }

    func testInterpolationHandlesEdgesAndNonfiniteValues() throws {
        let route = try XCTUnwrap(Self.missionWithGeometry().offlineRoute)
        XCTAssertEqual(route.coordinate(at: -1), route.coordinates.first)
        let end = try XCTUnwrap(route.coordinate(at: 1))
        XCTAssertEqual(end.latitude, try XCTUnwrap(route.coordinates.last).latitude, accuracy: 0.00000001)
        XCTAssertNil(route.coordinate(at: .nan))
        XCTAssertNil(route.coordinate(at: .infinity))
    }
}
