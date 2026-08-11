import Combine
import CoreLocation
import Foundation

@MainActor
protocol AudioControlling: AnyObject, ObservableObject {
    var elapsed: TimeInterval { get }
    var duration: TimeInterval { get }
    var isPlaying: Bool { get }
    var isPrepared: Bool { get }
    var pauseCount: Int { get }
    var errorMessage: String? { get }
    var incidents: [AudioIncident] { get }
    var onFinished: (() -> Void)? { get set }
    var onStopRequested: (() -> Void)? { get set }
    var onFatalError: ((String) -> Void)? { get set }

    var latestIncidentPublisher: AnyPublisher<AudioIncident?, Never> { get }

    func prepare(fileName: String, title: String, expectedDuration: TimeInterval?)
    func play() -> Bool
    func pause()
    func stop()
}

extension AudioController: AudioControlling {
    var latestIncidentPublisher: AnyPublisher<AudioIncident?, Never> {
        $incidents
            .map { $0.last }
            .eraseToAnyPublisher()
    }
}

@MainActor
protocol LocationRecording: AnyObject, ObservableObject {
    var authorizationStatus: CLAuthorizationStatus { get }
    var accuracyAuthorization: CLAccuracyAuthorization { get }
    var samples: [TrackSample] { get }
    var latestSample: TrackSample? { get }
    var isRecording: Bool { get }
    var isAwaitingAuthorization: Bool { get }
    var lastError: String? { get }
    var exportedURL: URL? { get }
    var lastSummary: TrackSummary? { get }
    var completedNormally: Bool { get }
    var incidents: [String] { get }

    var latestSamplePublisher: AnyPublisher<TrackSample?, Never> { get }
    var lastErrorPublisher: AnyPublisher<String?, Never> { get }

    func requestPermission()
    func start(prefix: String) -> LocationStartResult
    func stop(completed: Bool) -> TrackSummary?
    func cancelPendingStart()
}

extension LocationRecorder: LocationRecording {
    var latestSamplePublisher: AnyPublisher<TrackSample?, Never> {
        $latestSample.eraseToAnyPublisher()
    }

    var lastErrorPublisher: AnyPublisher<String?, Never> {
        $lastError.eraseToAnyPublisher()
    }
}
