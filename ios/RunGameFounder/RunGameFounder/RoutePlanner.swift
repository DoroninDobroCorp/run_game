import MapKit

@MainActor
final class RoutePlanner: ObservableObject {
    @Published private(set) var polylines: [MKPolyline] = []
    @Published private(set) var distanceMeters: CLLocationDistance = 0
    @Published private(set) var expectedTravelTime: TimeInterval = 0
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    func load(points: [RoutePoint]) async {
        guard points.count >= 2 else { return }
        isLoading = true
        errorMessage = nil
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
                guard let route = response.routes.first else { continue }
                newPolylines.append(route.polyline)
                newDistance += route.distance
                newTime += route.expectedTravelTime
            }
            polylines = newPolylines
            distanceMeters = newDistance
            expectedTravelTime = newTime
        } catch {
            errorMessage = "Apple Maps не смог построить пешеходный preview: \(error.localizedDescription)"
        }
        isLoading = false
    }
}
