import CoreLocation
import Foundation

enum LocationStartResult: Equatable {
    case started
    case awaitingAuthorization
    case unavailable(String)
}

@MainActor
final class LocationRecorder: NSObject, ObservableObject, @preconcurrency CLLocationManagerDelegate {
    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    @Published private(set) var accuracyAuthorization: CLAccuracyAuthorization
    @Published private(set) var samples: [TrackSample] = []
    @Published private(set) var latestSample: TrackSample?
    @Published private(set) var isRecording = false
    @Published private(set) var isAwaitingAuthorization = false
    @Published private(set) var lastError: String?
    @Published private(set) var exportedURL: URL?
    @Published private(set) var lastSummary: TrackSummary?
    @Published private(set) var completedNormally = false
    @Published private(set) var incidents: [String] = []

    private let manager = CLLocationManager()
    private var pendingStart = false
    private var currentPrefix = "run-game-track"
    private var recoveryURL: URL?
    private var checkpointSampleCount = 0

    override init() {
        authorizationStatus = manager.authorizationStatus
        accuracyAuthorization = manager.accuracyAuthorization
        super.init()
        manager.delegate = self
        manager.activityType = .fitness
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = 3
        manager.pausesLocationUpdatesAutomatically = false
        manager.showsBackgroundLocationIndicator = true
    }

    var hasFullAccuracy: Bool { accuracyAuthorization == .fullAccuracy }

    func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    @discardableResult
    func start(prefix: String) -> LocationStartResult {
        guard !isRecording else { return .started }
        currentPrefix = GPXDocument.sanitized(prefix)
        lastError = nil
        exportedURL = nil
        lastSummary = nil
        completedNormally = false
        incidents = []

        if authorizationStatus == .notDetermined {
            pendingStart = true
            isAwaitingAuthorization = true
            requestPermission()
            return .awaitingAuthorization
        }
        guard authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways else {
            let message = "Разрешите геолокацию в Settings, иначе локальный GPX не будет записан."
            lastError = message
            return .unavailable(message)
        }
        guard accuracyAuthorization == .fullAccuracy else {
            let message = "Для полевого evidence включите точную геопозицию (Precise Location) в Settings."
            lastError = message
            return .unavailable(message)
        }
        beginRecording()
        return .started
    }

    @discardableResult
    func stop(completed: Bool = true) -> TrackSummary? {
        pendingStart = false
        isAwaitingAuthorization = false
        if !isRecording, let lastSummary { return lastSummary }

        manager.stopUpdatingLocation()
        manager.allowsBackgroundLocationUpdates = false
        isRecording = false
        do {
            let url = try GPXDocument.save(samples: samples, prefix: currentPrefix)
            let summary = try TrackSummary.make(
                fileName: url.lastPathComponent,
                samples: samples,
                fileSHA256: BundleIntegrity.sha256(of: url)
            )
            guard FileDurability.verifySHA256(of: url, expectedSHA: summary.fileSHA256) else {
                throw FounderAppError.invalidTrack("GPX SHA-256 не прошёл проверку на диске")
            }
            exportedURL = url
            lastSummary = summary
            completedNormally = completed
            if let recoveryURL { try? FileManager.default.removeItem(at: recoveryURL) }
            recoveryURL = nil
            return summary
        } catch {
            lastError = error.localizedDescription
            completedNormally = false
            checkpointRecoveryFile()
            return nil
        }
    }

    func cancelPendingStart() {
        pendingStart = false
        isAwaitingAuthorization = false
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationStatus = manager.authorizationStatus
        accuracyAuthorization = manager.accuracyAuthorization

        if pendingStart && (authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways) {
            guard accuracyAuthorization == .fullAccuracy else {
                pendingStart = false
                isAwaitingAuthorization = false
                lastError = "Точная геопозиция выключена; запись и запуск миссии заблокированы."
                return
            }
            beginRecording()
        } else if isRecording,
                  (authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways),
                  accuracyAuthorization != .fullAccuracy {
            let message = "Точная геопозиция была выключена во время записи; сессия остановлена как partial."
            incidents.append(message)
            lastError = message
            _ = stop(completed: false)
        } else if authorizationStatus == .denied || authorizationStatus == .restricted {
            pendingStart = false
            isAwaitingAuthorization = false
            let message = "Геолокация не разрешена; миссия не запущена, локальный GPX не записывается."
            incidents.append(message)
            lastError = message
            if isRecording { _ = stop(completed: false) }
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard isRecording else { return }
        let now = Date()
        let candidates = locations
            .filter {
                CLLocationCoordinate2DIsValid($0.coordinate)
                    && $0.horizontalAccuracy >= 0 && $0.horizontalAccuracy <= 50
                    && $0.timestamp.timeIntervalSince(now) > -10
                    && $0.timestamp.timeIntervalSince(now) < 5
            }
            .sorted { $0.timestamp < $1.timestamp }

        var lastAcceptedTimestamp = samples.last?.timestamp ?? .distantPast
        var lastAcceptedLocation = samples.last?.location
        let accepted = candidates.compactMap { location -> TrackSample? in
            guard location.timestamp > lastAcceptedTimestamp else { return nil }
            if let previous = lastAcceptedLocation {
                let interval = location.timestamp.timeIntervalSince(lastAcceptedTimestamp)
                guard interval > 0, previous.distance(from: location) / interval <= 15 else {
                    return nil
                }
            }
            lastAcceptedTimestamp = location.timestamp
            lastAcceptedLocation = location
            return TrackSample(location: location)
        }

        guard !accepted.isEmpty else { return }
        samples.append(contentsOf: accepted)
        latestSample = samples.last
        if checkpointSampleCount == 0 || samples.count - checkpointSampleCount >= 5 {
            checkpointRecoveryFile()
            checkpointSampleCount = samples.count
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let coreError = error as? CLError
        if coreError?.code == .locationUnknown { return }
        let message = "Ошибка GPS: \(error.localizedDescription)"
        incidents.append(message)
        lastError = message
        if coreError?.code == .denied, isRecording {
            _ = stop(completed: false)
        }
    }

    private func beginRecording() {
        pendingStart = false
        isAwaitingAuthorization = false
        samples = []
        latestSample = nil
        exportedURL = nil
        lastSummary = nil
        completedNormally = false
        checkpointSampleCount = 0
        recoveryURL = Self.makeRecoveryURL(prefix: currentPrefix)
        manager.allowsBackgroundLocationUpdates = true
        manager.startUpdatingLocation()
        isRecording = true
    }

    private func checkpointRecoveryFile() {
        guard !samples.isEmpty, let recoveryURL else { return }
        do {
            let data = try GPXDocument.data(samples: samples, name: "Run Game — незавершённый recovered track")
            try FileDurability.writeAtomicDraft(data: data, to: recoveryURL)
        } catch {
            let message = "Не удалось сохранить recovery checkpoint: \(error.localizedDescription)"
            if incidents.last != message { incidents.append(message) }
        }
    }

    private static func makeRecoveryURL(prefix: String) -> URL {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let suffix = UUID().uuidString.prefix(8).lowercased()
        return documents.appendingPathComponent("\(prefix)-\(suffix).partial.gpx")
    }
}
