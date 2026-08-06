import CoreLocation
import Foundation

final class LocationRecorder: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    @Published private(set) var samples: [TrackSample] = []
    @Published private(set) var isRecording = false
    @Published private(set) var lastError: String?
    @Published private(set) var exportedURL: URL?

    private let manager = CLLocationManager()
    private var pendingStart = false

    override init() {
        authorizationStatus = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.activityType = .fitness
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = 3
        manager.pausesLocationUpdatesAutomatically = false
        manager.showsBackgroundLocationIndicator = true
    }

    func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    func start() {
        if authorizationStatus == .notDetermined {
            pendingStart = true
            requestPermission()
            return
        }
        guard authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways else {
            lastError = "Разрешите геолокацию для записи локального GPX."
            return
        }
        samples = []
        exportedURL = nil
        lastError = nil
        manager.allowsBackgroundLocationUpdates = true
        manager.startUpdatingLocation()
        isRecording = true
    }

    func stop(prefix: String) {
        manager.stopUpdatingLocation()
        manager.allowsBackgroundLocationUpdates = false
        isRecording = false
        do {
            exportedURL = try GPXDocument.save(samples: samples, prefix: prefix)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationStatus = manager.authorizationStatus
        if pendingStart && (authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways) {
            pendingStart = false
            start()
        } else if authorizationStatus == .denied || authorizationStatus == .restricted {
            pendingStart = false
            lastError = "Геолокация не разрешена; локальный GPX не будет записан."
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let accepted = locations.filter {
            $0.horizontalAccuracy >= 0 && $0.horizontalAccuracy <= 50 && $0.timestamp.timeIntervalSinceNow > -15
        }
        samples.append(contentsOf: accepted.map(TrackSample.init(location:)))
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        lastError = error.localizedDescription
    }
}
