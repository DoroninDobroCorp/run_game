import MapKit

@MainActor
final class RoutePlanner: ObservableObject {
    @Published private(set) var polylines: [MKPolyline] = []
    @Published private(set) var distanceMeters: CLLocationDistance = 0
    @Published private(set) var expectedTravelTime: TimeInterval = 0
    @Published private(set) var completedLegs = 0
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    var isComplete: Bool { completedLegs > 0 && completedLegs == polylines.count }

    func load(points: [RoutePoint]) async {
        guard points.count >= 2 else {
            polylines = []
            distanceMeters = 0
            expectedTravelTime = 0
            completedLegs = 0
            errorMessage = "В bundle недостаточно точек для замкнутого маршрута."
            return
        }
        isLoading = true
        errorMessage = nil
        completedLegs = 0
        var newPolylines: [MKPolyline] = []
        var newDistance: CLLocationDistance = 0
        var newTime: TimeInterval = 0

        do {
            for pair in zip(points, points.dropFirst()) {
                let request = MKDirections.Request()
                request.source = MKMapItem(placemark: MKPlacemark(coordinate: pair.0.coordinate))
                request.destination = MKMapItem(placemark: MKPlacemark(coordinate: pair.1.coordinate))
                request.transportType = .walking
                request.requestsAlternateRoutes = false
                let response = try await MKDirections(request: request).calculate()
                guard let route = response.routes.first else {
                    throw RoutePlannerError.missingLeg(pair.0.name, pair.1.name)
                }
                newPolylines.append(route.polyline)
                newDistance += route.distance
                newTime += route.expectedTravelTime
            }
            guard newPolylines.count == points.count - 1 else {
                throw RoutePlannerError.incompleteRoute(newPolylines.count, points.count - 1)
            }
            polylines = newPolylines
            distanceMeters = newDistance
            expectedTravelTime = newTime
            completedLegs = newPolylines.count
        } catch {
            polylines = []
            distanceMeters = 0
            expectedTravelTime = 0
            completedLegs = 0
            errorMessage = "Apple Maps не смог построить пешеходный preview: \(error.localizedDescription)"
        }
        isLoading = false
    }
}

private enum RoutePlannerError: LocalizedError {
    case missingLeg(String, String)
    case incompleteRoute(Int, Int)

    var errorDescription: String? {
        switch self {
        case .missingLeg(let start, let end):
            return "нет пешеходного сегмента «\(start)» → «\(end)»"
        case .incompleteRoute(let actual, let expected):
            return "построено только \(actual) из \(expected) сегментов"
        }
    }
}
