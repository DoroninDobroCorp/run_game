import Combine
import CoreLocation
import Foundation

/// SessionCoordinator coordinates hardware controllers (LocationRecorder, AudioController)
/// and session persistence (ActiveRunJournal, AppModel) around pure SessionStateMachine transitions.
@MainActor
final class SessionCoordinator: ObservableObject {
    @Published private(set) var stateMachine: SessionStateMachine
    @Published private(set) var currentRunState: SessionStateMachine.State
    @Published private(set) var isRecording: Bool
    @Published private(set) var recordedPointsCount: Int
    @Published private(set) var audioElapsedSeconds: TimeInterval
    @Published private(set) var activeIncidentCount: Int
    @Published private(set) var statusMessage: String?

    let mission: MissionConfig
    let audio: any AudioControlling
    let recorder: any LocationRecording
    let appModel: AppModel

    private var cancellables = Set<AnyCancellable>()
    private var firstFixTimeout: Task<Void, Never>?
    private var precommittedNextWorkoutAt: Date

    init(
        mission: MissionConfig,
        appModel: AppModel,
        audio: any AudioControlling = AudioController(),
        recorder: any LocationRecording = LocationRecorder(),
        initialState: SessionStateMachine.State = .ready,
        precommittedNextWorkoutAt: Date = Calendar.current.date(byAdding: .day, value: 2, to: Date()) ?? Date()
    ) {
        self.mission = mission
        self.appModel = appModel
        self.audio = audio
        self.recorder = recorder
        self.stateMachine = SessionStateMachine(initialState: initialState)
        self.currentRunState = initialState
        self.isRecording = recorder.isRecording
        self.recordedPointsCount = recorder.samples.count
        self.audioElapsedSeconds = audio.elapsed
        self.activeIncidentCount = audio.incidents.count + recorder.incidents.count
        self.precommittedNextWorkoutAt = precommittedNextWorkoutAt

        setupSubscriptions()
        prepareAudio()
        updatePublishedSnapshots()
    }

    deinit {
        firstFixTimeout?.cancel()
    }

    var state: SessionStateMachine.State {
        currentRunState
    }

    var isReady: Bool { stateMachine.isReady }
    var isAcquiringGPS: Bool { stateMachine.isAcquiringGPS }
    var isRunning: Bool { stateMachine.isRunning }
    var isCompleted: Bool { stateMachine.isCompleted }
    var isAborted: Bool { stateMachine.isAborted }

    var currentContext: RunSessionContext? {
        switch stateMachine.state {
        case .completed(let context):
            return context
        case .aborted(let context, _):
            return context
        default:
            return nil
        }
    }

    func updatePrecommittedNextWorkoutAt(_ date: Date) {
        precommittedNextWorkoutAt = date
    }

    func send(_ event: SessionStateMachine.Event) {
        let actions = stateMachine.handle(
            event: event,
            mission: mission,
            precommittedNextWorkoutAt: precommittedNextWorkoutAt
        )
        execute(actions)
        updatePublishedSnapshots()
    }

    func abortSession(reason: String) {
        guard isRunning || isAcquiringGPS else { return }
        let (summary, routeTraversal) = stopRecorderAndMakeEvidence(completed: false)
        let audioIncidents = audio.incidents.map {
            "\($0.kind.rawValue) @ \(Formatters.clock($0.elapsed)): \($0.message)"
        }
        send(.userAborted(
            reason: reason,
            summary: summary,
            routeTraversal: routeTraversal,
            audioIncidents: audioIncidents,
            locationIncidents: recorder.incidents,
            elapsed: audio.elapsed
        ))
    }

    private func updatePublishedSnapshots() {
        currentRunState = stateMachine.state
        isRecording = recorder.isRecording
        recordedPointsCount = recorder.samples.count
        audioElapsedSeconds = audio.elapsed
        activeIncidentCount = audio.incidents.count + recorder.incidents.count
    }

    private func stopRecorderAndMakeEvidence(completed: Bool) -> (summary: TrackSummary?, routeTraversal: WalkthroughEvidence?) {
        let summary = recorder.stop(completed: completed)
        let routeTraversal = summary.map {
            WalkthroughEvidence.make(
                mission: mission,
                summary: $0,
                samples: recorder.samples,
                locationIncidents: recorder.incidents
            )
        }
        return (summary, routeTraversal)
    }

    // MARK: - Actions Execution
    private func execute(_ actions: [SessionStateMachine.Action]) {
        for action in actions {
            switch action {
            case .startGPSRecording(let prefix):
                let result = recorder.start(prefix: prefix)
                if case .unavailable(let message) = result {
                    send(.gpsFailed(reason: message))
                }
            case .cancelGPSRecording:
                recorder.cancelPendingStart()
            case .stopGPSRecording(let completed):
                if recorder.isRecording {
                    _ = recorder.stop(completed: completed)
                }
            case .startFirstFixTimer(let seconds):
                firstFixTimeout?.cancel()
                firstFixTimeout = Task { @MainActor [weak self] in
                    try? await Task.sleep(for: .seconds(seconds))
                    guard let self, !Task.isCancelled, self.isAcquiringGPS else { return }
                    self.send(.gpsFirstFixTimeout)
                }
            case .cancelFirstFixTimer:
                firstFixTimeout?.cancel()
                firstFixTimeout = nil
            case .startAudioPlayback:
                let started: Bool = audio.play()
                if started {
                    send(.audioStarted())
                } else {
                    send(.audioStartFailed(reason: audio.errorMessage ?? "Master-аудио не запустилось."))
                }
            case .pauseAudioPlayback:
                audio.pause()
            case .stopAudioPlayback:
                audio.stop()
            case .saveJournal(let attempt):
                appModel.saveActiveAttempt(attempt)
            case .clearJournal:
                appModel.clearActiveJournal()
            case .scheduleDebrief(let context):
                appModel.scheduleDebrief(for: context)
            case .scheduleRecall(let context):
                appModel.scheduleRecall(for: context)
            case .setStatusMessage(let message):
                self.statusMessage = message
            }
        }
    }

    // MARK: - Subscriptions & Handlers
    private func setupSubscriptions() {
        // Observe changes on audio and recorder to keep published properties updated
        audio.objectWillChangePublisher
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                self?.updatePublishedSnapshots()
            }
            .store(in: &cancellables)

        recorder.objectWillChangePublisher
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                self?.updatePublishedSnapshots()
            }
            .store(in: &cancellables)

        // Prepare Audio handlers
        audio.onFinished = { [weak self] in
            guard let self, self.isRunning else { return }
            let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: true)
            let audioIncidents = self.audio.incidents.map {
                "\($0.kind.rawValue) @ \(Formatters.clock($0.elapsed)): \($0.message)"
            }
            self.send(.audioFinishedNaturally(
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: audioIncidents,
                locationIncidents: self.recorder.incidents,
                elapsed: self.audio.elapsed
            ))
        }

        audio.onStopRequested = { [weak self] in
            guard let self, self.isRunning else { return }
            let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: false)
            self.send(.remoteStopRequested(
                elapsed: self.audio.elapsed,
                summary: summary,
                routeTraversal: routeTraversal
            ))
        }

        audio.onFatalError = { [weak self] message in
            guard let self else { return }
            if self.isRunning {
                let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: false)
                self.send(.audioStartFailed(
                    reason: message,
                    elapsed: self.audio.elapsed,
                    summary: summary,
                    routeTraversal: routeTraversal
                ))
            } else if self.isAcquiringGPS {
                self.send(.audioStartFailed(reason: message))
            } else {
                self.statusMessage = message
                self.updatePublishedSnapshots()
            }
        }

        // Recorder sample changes -> GPS fix evaluation
        recorder.latestSamplePublisher
            .compactMap { $0 }
            .sink { [weak self] sample in
                guard let self else { return }
                self.updatePublishedSnapshots()
                guard self.isAcquiringGPS, let start = self.mission.routePoints.first else { return }
                let distance = sample.location.distance(from: start.location)
                self.send(.receiveGPSFix(accuracy: sample.horizontalAccuracy, distanceToStartMeters: distance))
            }
            .store(in: &cancellables)

        // Recorder error handling
        recorder.lastErrorPublisher
            .compactMap { $0 }
            .sink { [weak self] error in
                guard let self else { return }
                if self.isAcquiringGPS {
                    self.send(.gpsFailed(reason: error))
                } else if self.isRunning {
                    let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: false)
                    self.send(.gpsFailed(
                        reason: "GPS session failed: \(error)",
                        elapsed: self.audio.elapsed,
                        summary: summary,
                        routeTraversal: routeTraversal
                    ))
                }
            }
            .store(in: &cancellables)

        // Audio incidents handling
        audio.latestIncidentPublisher
            .compactMap { $0 }
            .sink { [weak self] incident in
                guard let self, self.isRunning else { return }
                switch incident.kind {
                case .interruptionBegan:
                    let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: false)
                    self.send(.audioInterrupted(
                        reason: incident.message,
                        elapsed: self.audio.elapsed,
                        summary: summary,
                        routeTraversal: routeTraversal
                    ))
                case .outputRouteDisconnected:
                    let (summary, routeTraversal) = self.stopRecorderAndMakeEvidence(completed: false)
                    self.send(.routeDisconnected(
                        elapsed: self.audio.elapsed,
                        summary: summary,
                        routeTraversal: routeTraversal
                    ))
                default:
                    break
                }
            }
            .store(in: &cancellables)
    }

    private func prepareAudio() {
        audio.prepare(
            fileName: mission.audioFile,
            title: mission.title,
            expectedDuration: mission.durationSeconds
        )
    }
}
