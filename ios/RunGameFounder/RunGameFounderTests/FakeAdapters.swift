import Combine
import CoreLocation
import Foundation
@testable import RunGameFounder

@MainActor
final class FakeAudioController: AudioControlling {
    var elapsed: TimeInterval = 0
    var duration: TimeInterval = 1800
    var isPlaying: Bool = false
    var isPrepared: Bool = false
    var pauseCount: Int = 0
    var errorMessage: String? = nil
    var incidents: [AudioIncident] = []

    var onFinished: (() -> Void)?
    var onStopRequested: (() -> Void)?
    var onFatalError: ((String) -> Void)?

    let latestIncidentSubject = CurrentValueSubject<AudioIncident?, Never>(nil)
    var latestIncidentPublisher: AnyPublisher<AudioIncident?, Never> {
        latestIncidentSubject.eraseToAnyPublisher()
    }

    var playSucceeds = true
    var prepareSucceeds = true

    func prepare(fileName: String, title: String, expectedDuration: TimeInterval?) {
        if prepareSucceeds {
            isPrepared = true
            duration = expectedDuration ?? 1800
        } else {
            isPrepared = false
            errorMessage = "Preparation failed"
            onFatalError?(errorMessage!)
        }
    }

    func play() -> Bool {
        if playSucceeds {
            isPlaying = true
            errorMessage = nil
            return true
        } else {
            errorMessage = "Playback failed"
            return false
        }
    }

    func pause() {
        isPlaying = false
        pauseCount += 1
    }

    func stop() {
        isPlaying = false
        elapsed = 0
    }
}

@MainActor
final class FakeLocationRecorder: LocationRecording {
    var authorizationStatus: CLAuthorizationStatus = .authorizedWhenInUse
    var accuracyAuthorization: CLAccuracyAuthorization = .fullAccuracy
    var samples: [TrackSample] = []
    var latestSample: TrackSample? = nil
    var isRecording: Bool = false
    var isAwaitingAuthorization: Bool = false
    var lastError: String? = nil
    var exportedURL: URL? = nil
    var lastSummary: TrackSummary? = nil
    var completedNormally: Bool = false
    var incidents: [String] = []

    let latestSampleSubject = CurrentValueSubject<TrackSample?, Never>(nil)
    var latestSamplePublisher: AnyPublisher<TrackSample?, Never> {
        latestSampleSubject.eraseToAnyPublisher()
    }

    let lastErrorSubject = CurrentValueSubject<String?, Never>(nil)
    var lastErrorPublisher: AnyPublisher<String?, Never> {
        lastErrorSubject.eraseToAnyPublisher()
    }

    var startResult: LocationStartResult = .started

    func requestPermission() {}

    func start(prefix: String) -> LocationStartResult {
        if startResult == .started {
            isRecording = true
            return .started
        }
        return startResult
    }

    func stop(completed: Bool) -> TrackSummary? {
        isRecording = false
        completedNormally = completed
        return lastSummary
    }

    func cancelPendingStart() {
        isRecording = false
    }
}
