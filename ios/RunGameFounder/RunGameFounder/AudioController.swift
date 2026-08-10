import AVFoundation
import Foundation
import MediaPlayer

struct AudioIncident: Codable, Equatable {
    enum Kind: String, Codable {
        case preparationFailed
        case durationMismatch
        case playbackStartFailed
        case playbackEndedUnsuccessfully
        case interruptionBegan
        case interruptionEnded
        case outputRouteDisconnected
        case mediaServicesReset
        case decodeError
        case remoteStopRequested
        case sessionDeactivationFailed
    }

    let kind: Kind
    let occurredAt: Date
    let elapsed: TimeInterval
    let message: String
}

@MainActor
final class AudioController: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var duration: TimeInterval = 0
    @Published private(set) var isPlaying = false
    @Published private(set) var isPrepared = false
    @Published private(set) var pauseCount = 0
    @Published private(set) var errorMessage: String?
    @Published private(set) var incidents: [AudioIncident] = []

    var onFinished: (() -> Void)?
    var onStopRequested: (() -> Void)?
    var onFatalError: ((String) -> Void)?

    private struct RemoteTarget {
        let command: MPRemoteCommand
        let token: Any
    }

    private static let durationTolerance: TimeInterval = 0.5

    private var player: AVAudioPlayer?
    private var timer: Timer?
    private var remoteTargets: [RemoteTarget] = []
    private var remoteCommandsConfigured = false
    private var audioSessionNotificationsConfigured = false
    private var audioSessionIsActive = false
    private var nowPlayingTitle: String?
    private var wasPlayingBeforeInterruption = false
    private var interruptionInProgress = false
    private var fatalErrorReported = false

    override init() {
        super.init()
        configureAudioSessionNotifications()
    }

    isolated deinit {
        timer?.invalidate()
        NotificationCenter.default.removeObserver(self)
        for target in remoteTargets {
            target.command.removeTarget(target.token)
        }
        if remoteCommandsConfigured {
            let commands = MPRemoteCommandCenter.shared()
            commands.playCommand.isEnabled = false
            commands.pauseCommand.isEnabled = false
            commands.stopCommand.isEnabled = false
        }
        if audioSessionIsActive {
            try? AVAudioSession.sharedInstance().setActive(
                false,
                options: .notifyOthersOnDeactivation
            )
        }
        if remoteCommandsConfigured || MPNowPlayingInfoCenter.default().nowPlayingInfo != nil {
            MPNowPlayingInfoCenter.default().playbackState = .stopped
            MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
        }
    }

    func prepare(
        fileName: String,
        title: String,
        expectedDuration: TimeInterval? = nil
    ) {
        guard player == nil else { return }

        fatalErrorReported = false
        errorMessage = nil
        isPrepared = false
        elapsed = 0
        duration = 0
        pauseCount = 0
        nowPlayingTitle = nil
        let fileURL = URL(fileURLWithPath: fileName)
        let resource = fileURL.deletingPathExtension().lastPathComponent
        let ext = fileURL.pathExtension
        guard let url = Bundle.main.url(forResource: resource, withExtension: ext) else {
            reportFatal(
                kind: .preparationFailed,
                message: "Master-аудио \(fileName) не найдено в приложении."
            )
            return
        }

        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio)

            let preparedPlayer = try AVAudioPlayer(contentsOf: url)
            guard preparedPlayer.prepareToPlay() else {
                reportFatal(
                    kind: .preparationFailed,
                    message: "Master-аудио не удалось подготовить к воспроизведению."
                )
                return
            }

            let measuredDuration = preparedPlayer.duration
            guard measuredDuration.isFinite, measuredDuration > 0 else {
                reportFatal(
                    kind: .preparationFailed,
                    message: "Master-аудио имеет некорректную длительность."
                )
                return
            }
            if let expectedDuration {
                guard expectedDuration.isFinite, expectedDuration > 0 else {
                    reportFatal(
                        kind: .durationMismatch,
                        message: "Ожидаемая длительность master-аудио некорректна."
                    )
                    return
                }
                guard abs(measuredDuration - expectedDuration) <= Self.durationTolerance else {
                    reportFatal(
                        kind: .durationMismatch,
                        message: String(
                            format: "Длительность master-аудио не совпадает: %.1f с вместо %.1f с.",
                            measuredDuration,
                            expectedDuration
                        )
                    )
                    return
                }
            }

            preparedPlayer.delegate = self
            player = preparedPlayer
            duration = measuredDuration
            elapsed = preparedPlayer.currentTime
            nowPlayingTitle = title
            isPrepared = true
        } catch {
            reportFatal(kind: .preparationFailed, message: error.localizedDescription)
        }
    }

    @discardableResult
    func play() -> Bool {
        startPlayback()
    }

    func pause() {
        let wasPlaying = isPlaying
        player?.pause()
        refreshElapsed()
        isPlaying = false
        stopTimer()
        updatePlaybackState()
        pauseCount = Self.pauseCount(after: pauseCount, wasPlaying: wasPlaying)
    }

    static func pauseCount(after current: Int, wasPlaying: Bool) -> Int {
        wasPlaying ? current + 1 : current
    }

    func stop() {
        player?.stop()
        player?.currentTime = 0
        elapsed = 0
        isPlaying = false
        wasPlayingBeforeInterruption = false
        interruptionInProgress = false
        stopTimer()
        removeRemoteCommands()
        deactivateAudioSession(clearNowPlaying: true)
    }

    /// Seeking is intentionally disabled for the linear home-audit and mission timelines.
    func seek(to _: TimeInterval) {}

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        let finishedAt = flag ? player.duration : player.currentTime
        DispatchQueue.main.async { [weak self] in
            self?.handlePlaybackFinished(successfully: flag, finishedAt: finishedAt)
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        let message = error?.localizedDescription ?? "Неизвестная ошибка декодирования master-аудио."
        DispatchQueue.main.async { [weak self] in
            self?.handleDecodeError(message: message)
        }
    }

    private func startPlayback() -> Bool {
        guard isPrepared, let player else {
            reportFatal(
                kind: .playbackStartFailed,
                message: "Master-аудио не подготовлено к воспроизведению."
            )
            return false
        }

        do {
            try AVAudioSession.sharedInstance().setActive(true)
            audioSessionIsActive = true
            configureRemoteCommands()
            if let nowPlayingTitle {
                updateNowPlaying(title: nowPlayingTitle)
            }
            guard player.play() else {
                reportFatal(
                    kind: .playbackStartFailed,
                    message: "Системный аудиоплеер не смог начать воспроизведение."
                )
                return false
            }
            errorMessage = nil
            isPlaying = true
            startTimer()
            updatePlaybackState()
            return true
        } catch {
            reportFatal(kind: .playbackStartFailed, message: error.localizedDescription)
            return false
        }
    }

    private func handlePlaybackFinished(successfully: Bool, finishedAt: TimeInterval) {
        guard isPlaying else { return }
        elapsed = min(duration, max(0, finishedAt))
        isPlaying = false
        wasPlayingBeforeInterruption = false
        interruptionInProgress = false
        stopTimer()

        if successfully {
            removeRemoteCommands()
            deactivateAudioSession(clearNowPlaying: true)
            onFinished?()
        } else {
            reportFatal(
                kind: .playbackEndedUnsuccessfully,
                message: "Воспроизведение master-аудио завершилось с ошибкой."
            )
        }
    }

    private func handleDecodeError(message: String) {
        reportFatal(
            kind: .decodeError,
            message: "Ошибка декодирования master-аудио: \(message)"
        )
    }

    private func startTimer() {
        stopTimer()
        let newTimer = Timer(timeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.refreshElapsed()
                self?.updatePlaybackState()
            }
        }
        timer = newTimer
        RunLoop.main.add(newTimer, forMode: .common)
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func refreshElapsed() {
        elapsed = player?.currentTime ?? elapsed
    }

    private func configureRemoteCommands() {
        guard !remoteCommandsConfigured else { return }
        remoteCommandsConfigured = true

        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.isEnabled = true
        commands.pauseCommand.isEnabled = true
        commands.stopCommand.isEnabled = true
        commands.changePlaybackPositionCommand.isEnabled = false
        commands.skipForwardCommand.isEnabled = false
        commands.skipBackwardCommand.isEnabled = false
        commands.seekForwardCommand.isEnabled = false
        commands.seekBackwardCommand.isEnabled = false
        commands.nextTrackCommand.isEnabled = false
        commands.previousTrackCommand.isEnabled = false
        commands.togglePlayPauseCommand.isEnabled = false

        let playTarget = commands.playCommand.addTarget { [weak self] _ in
            Self.performRemoteAction {
                guard let self else { return .noSuchContent }
                let started: Bool = self.play()
                return started ? .success : .commandFailed
            }
        }
        remoteTargets.append(RemoteTarget(command: commands.playCommand, token: playTarget))

        let pauseTarget = commands.pauseCommand.addTarget { [weak self] _ in
            Self.performRemoteAction {
                guard let self, self.isPrepared else { return .noSuchContent }
                self.pause()
                return .success
            }
        }
        remoteTargets.append(RemoteTarget(command: commands.pauseCommand, token: pauseTarget))

        let stopTarget = commands.stopCommand.addTarget { [weak self] _ in
            Self.performRemoteAction {
                guard let self, self.isPrepared else { return .noSuchContent }
                self.handleRemoteStopRequest()
                return .success
            }
        }
        remoteTargets.append(RemoteTarget(command: commands.stopCommand, token: stopTarget))
    }

    private func removeRemoteCommands() {
        guard remoteCommandsConfigured else { return }
        for target in remoteTargets {
            target.command.removeTarget(target.token)
        }
        remoteTargets.removeAll()
        remoteCommandsConfigured = false

        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.isEnabled = false
        commands.pauseCommand.isEnabled = false
        commands.stopCommand.isEnabled = false
        commands.changePlaybackPositionCommand.isEnabled = false
        commands.skipForwardCommand.isEnabled = false
        commands.skipBackwardCommand.isEnabled = false
        commands.seekForwardCommand.isEnabled = false
        commands.seekBackwardCommand.isEnabled = false
        commands.nextTrackCommand.isEnabled = false
        commands.previousTrackCommand.isEnabled = false
        commands.togglePlayPauseCommand.isEnabled = false
    }

    nonisolated private static func performRemoteAction(
        _ action: @escaping @MainActor @Sendable () -> MPRemoteCommandHandlerStatus
    ) -> MPRemoteCommandHandlerStatus {
        if Thread.isMainThread {
            return MainActor.assumeIsolated {
                action()
            }
        }
        return DispatchQueue.main.sync {
            MainActor.assumeIsolated {
                action()
            }
        }
    }

    private func handleRemoteStopRequest() {
        player?.pause()
        refreshElapsed()
        isPlaying = false
        wasPlayingBeforeInterruption = false
        interruptionInProgress = false
        stopTimer()
        appendIncident(
            kind: .remoteStopRequested,
            message: "Остановка запрошена с системного экрана управления."
        )
        removeRemoteCommands()
        deactivateAudioSession(clearNowPlaying: true)
        onStopRequested?()
    }

    private func configureAudioSessionNotifications() {
        guard !audioSessionNotificationsConfigured else { return }
        audioSessionNotificationsConfigured = true
        let center = NotificationCenter.default
        let session = AVAudioSession.sharedInstance()
        center.addObserver(
            self,
            selector: #selector(receiveInterruptionNotification(_:)),
            name: AVAudioSession.interruptionNotification,
            object: session
        )
        center.addObserver(
            self,
            selector: #selector(receiveRouteChangeNotification(_:)),
            name: AVAudioSession.routeChangeNotification,
            object: session
        )
        center.addObserver(
            self,
            selector: #selector(receiveMediaServicesResetNotification(_:)),
            name: AVAudioSession.mediaServicesWereResetNotification,
            object: session
        )
    }

    @objc nonisolated private func receiveInterruptionNotification(_ notification: Notification) {
        let typeRaw = Self.uintValue(
            notification.userInfo?[AVAudioSessionInterruptionTypeKey]
        )
        let optionsRaw = Self.uintValue(
            notification.userInfo?[AVAudioSessionInterruptionOptionKey]
        )
        DispatchQueue.main.async { [weak self] in
            self?.handleInterruption(typeRaw: typeRaw, optionsRaw: optionsRaw)
        }
    }

    @objc nonisolated private func receiveRouteChangeNotification(_ notification: Notification) {
        let reasonRaw = Self.uintValue(
            notification.userInfo?[AVAudioSessionRouteChangeReasonKey]
        )
        DispatchQueue.main.async { [weak self] in
            self?.handleRouteChange(reasonRaw: reasonRaw)
        }
    }

    @objc nonisolated private func receiveMediaServicesResetNotification(_: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.handleMediaServicesReset()
        }
    }

    nonisolated private static func uintValue(_ value: Any?) -> UInt? {
        if let number = value as? NSNumber { return number.uintValue }
        return value as? UInt
    }

    private func handleInterruption(typeRaw: UInt?, optionsRaw: UInt?) {
        guard isPrepared,
              let typeRaw,
              let type = AVAudioSession.InterruptionType(rawValue: typeRaw) else { return }

        switch type {
        case .began:
            wasPlayingBeforeInterruption = isPlaying
            interruptionInProgress = true
            audioSessionIsActive = false
            if isPlaying {
                player?.pause()
                refreshElapsed()
                isPlaying = false
                stopTimer()
            }
            errorMessage = "Аудиосессия прервана системным событием. Продолжите вручную, когда это безопасно."
            appendIncident(kind: .interruptionBegan, message: errorMessage ?? "Аудио приостановлено.")
            updatePlaybackState()
        case .ended:
            guard interruptionInProgress else { return }
            interruptionInProgress = false
            let interruptedActivePlayback = wasPlayingBeforeInterruption
            wasPlayingBeforeInterruption = false
            let shouldResume = optionsRaw.map {
                AVAudioSession.InterruptionOptions(rawValue: $0).contains(.shouldResume)
            } ?? false
            let recommendation = shouldResume
                ? "Система разрешила возобновление; автоматический restart отключён."
                : "Система не рекомендовала автоматическое возобновление."
            appendIncident(kind: .interruptionEnded, message: recommendation)
            if interruptedActivePlayback {
                errorMessage = "Аудио остаётся на паузе после системного события. Продолжите вручную."
            }
        @unknown default:
            break
        }
    }

    private func handleRouteChange(reasonRaw: UInt?) {
        guard let reasonRaw,
              AVAudioSession.RouteChangeReason(rawValue: reasonRaw) == .oldDeviceUnavailable,
              isPrepared else { return }

        player?.pause()
        refreshElapsed()
        isPlaying = false
        wasPlayingBeforeInterruption = false
        interruptionInProgress = false
        stopTimer()
        errorMessage = "Наушники отключены. Аудио остановлено; продолжите вручную после проверки выхода звука."
        appendIncident(
            kind: .outputRouteDisconnected,
            message: errorMessage ?? "Аудиовыход отключён."
        )
        updatePlaybackState()
        deactivateAudioSession(clearNowPlaying: false)
    }

    private func handleMediaServicesReset() {
        audioSessionIsActive = false
        interruptionInProgress = false
        reportFatal(
            kind: .mediaServicesReset,
            message: "Системная аудиослужба была перезапущена. Текущую сессию нельзя продолжать автоматически."
        )
    }

    private func reportFatal(kind: AudioIncident.Kind, message: String) {
        guard !fatalErrorReported else { return }
        fatalErrorReported = true
        player?.pause()
        refreshElapsed()
        player?.delegate = nil
        player = nil
        isPrepared = false
        isPlaying = false
        wasPlayingBeforeInterruption = false
        interruptionInProgress = false
        stopTimer()
        errorMessage = message
        appendIncident(kind: kind, message: message)
        removeRemoteCommands()
        deactivateAudioSession(clearNowPlaying: true)
        onFatalError?(message)
    }

    private func appendIncident(kind: AudioIncident.Kind, message: String) {
        incidents.append(
            AudioIncident(
                kind: kind,
                occurredAt: Date(),
                elapsed: elapsed,
                message: message
            )
        )
    }

    private func deactivateAudioSession(clearNowPlaying: Bool) {
        if audioSessionIsActive {
            do {
                try AVAudioSession.sharedInstance().setActive(
                    false,
                    options: .notifyOthersOnDeactivation
                )
                audioSessionIsActive = false
            } catch {
                appendIncident(
                    kind: .sessionDeactivationFailed,
                    message: "Не удалось деактивировать аудиосессию: \(error.localizedDescription)"
                )
            }
        }
        if clearNowPlaying {
            MPNowPlayingInfoCenter.default().playbackState = .stopped
            MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
        }
    }

    private func updateNowPlaying(title: String) {
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle: title,
            MPMediaItemPropertyArtist: "Run Game · Нулевой слой",
            MPMediaItemPropertyPlaybackDuration: duration,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: elapsed,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
        ]
        MPNowPlayingInfoCenter.default().playbackState = isPlaying ? .playing : .paused
    }

    private func updatePlaybackState() {
        guard var info = MPNowPlayingInfoCenter.default().nowPlayingInfo else { return }
        info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = elapsed
        info[MPNowPlayingInfoPropertyPlaybackRate] = isPlaying ? 1.0 : 0.0
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
        MPNowPlayingInfoCenter.default().playbackState = isPlaying ? .playing : .paused
    }
}
