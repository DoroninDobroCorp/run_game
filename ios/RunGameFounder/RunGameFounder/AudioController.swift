import AVFoundation
import Foundation
import MediaPlayer

final class AudioController: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var duration: TimeInterval = 0
    @Published private(set) var isPlaying = false
    @Published private(set) var errorMessage: String?

    var onFinished: (() -> Void)?

    private var player: AVAudioPlayer?
    private var timer: Timer?
    private var remoteCommandsConfigured = false

    func prepare(fileName: String, title: String) {
        guard player == nil else { return }
        let fileURL = URL(fileURLWithPath: fileName)
        let resource = fileURL.deletingPathExtension().lastPathComponent
        let ext = fileURL.pathExtension
        guard let url = Bundle.main.url(forResource: resource, withExtension: ext) else {
            errorMessage = "Master-аудио \(fileName) не найдено в приложении."
            return
        }

        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio)
            player = try AVAudioPlayer(contentsOf: url)
            player?.delegate = self
            player?.prepareToPlay()
            duration = player?.duration ?? 0
            configureRemoteCommands()
            updateNowPlaying(title: title)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func play() {
        guard let player else { return }
        do {
            try AVAudioSession.sharedInstance().setActive(true)
            player.play()
            isPlaying = true
            startTimer()
            updatePlaybackState()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func pause() {
        player?.pause()
        isPlaying = false
        stopTimer()
        updatePlaybackState()
    }

    func stop() {
        player?.stop()
        player?.currentTime = 0
        elapsed = 0
        isPlaying = false
        stopTimer()
        updatePlaybackState()
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func seek(to value: TimeInterval) {
        player?.currentTime = min(max(0, value), duration)
        elapsed = player?.currentTime ?? 0
        updatePlaybackState()
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        elapsed = player.duration
        isPlaying = false
        stopTimer()
        updatePlaybackState()
        if flag { onFinished?() }
    }

    private func startTimer() {
        stopTimer()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.elapsed = self.player?.currentTime ?? 0
            self.updatePlaybackState()
        }
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func configureRemoteCommands() {
        guard !remoteCommandsConfigured else { return }
        remoteCommandsConfigured = true
        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.addTarget { [weak self] _ in
            self?.play()
            return .success
        }
        commands.pauseCommand.addTarget { [weak self] _ in
            self?.pause()
            return .success
        }
        commands.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let event = event as? MPChangePlaybackPositionCommandEvent else { return .commandFailed }
            self?.seek(to: event.positionTime)
            return .success
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
    }

    private func updatePlaybackState() {
        guard var info = MPNowPlayingInfoCenter.default().nowPlayingInfo else { return }
        info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = elapsed
        info[MPNowPlayingInfoPropertyPlaybackRate] = isPlaying ? 1.0 : 0.0
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}
