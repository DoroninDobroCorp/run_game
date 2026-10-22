import CoreLocation
import Foundation

struct RouteCoordinate: Codable, Equatable {
    let latitude: Double
    let longitude: Double

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    var location: CLLocation { CLLocation(latitude: latitude, longitude: longitude) }
    var isValid: Bool {
        latitude.isFinite && longitude.isFinite
            && (-90...90).contains(latitude) && (-180...180).contains(longitude)
    }
}

/// Precompiled geometry. Map tiles are optional; the route itself never needs a network request.
struct OfflineRoute: Codable, Equatable {
    let coordinates: [RouteCoordinate]
    let waypointIndices: [Int]
    let source: String
    let attribution: String
    let note: String

    var distanceMeters: Double {
        zip(coordinates, coordinates.dropFirst()).reduce(0) { $0 + $1.0.location.distance(from: $1.1.location) }
    }

    func validate(waypoints: [RoutePoint]) throws {
        guard (5...10_000).contains(coordinates.count), coordinates.allSatisfy(\.isValid),
              waypointIndices.count == waypoints.count,
              waypointIndices.allSatisfy({ coordinates.indices.contains($0) }),
              waypointIndices.first == 0, waypointIndices.last == coordinates.count - 1,
              zip(waypointIndices, waypointIndices.dropFirst()).allSatisfy({ $0 < $1 }),
              !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !attribution.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw FounderAppError.invalidMission("Некорректная геометрия офлайн-маршрута")
        }
        guard zip(waypointIndices, waypoints).allSatisfy({ coordinates[$0].location.distance(from: $1.location) <= 10 }),
              coordinates[0].location.distance(from: coordinates[coordinates.count - 1].location) <= 25,
              zip(coordinates, coordinates.dropFirst()).allSatisfy({ $0.location.distance(from: $1.location) <= 500 }),
              (200...20_000).contains(distanceMeters) else {
            throw FounderAppError.invalidMission("Офлайн-маршрут разорван или не проходит контрольные точки")
        }
    }

    func coordinate(at fraction: Double) -> RouteCoordinate? {
        guard let first = coordinates.first, fraction.isFinite else { return nil }
        let target = min(1, max(0, fraction)) * distanceMeters
        var traversed = 0.0
        for (a, b) in zip(coordinates, coordinates.dropFirst()) {
            let length = a.location.distance(from: b.location)
            if length > 0 && traversed + length >= target {
                let progress = (target - traversed) / length
                return RouteCoordinate(
                    latitude: a.latitude + (b.latitude - a.latitude) * progress,
                    longitude: a.longitude + (b.longitude - a.longitude) * progress
                )
            }
            traversed += length
        }
        return coordinates.last ?? first
    }
}
