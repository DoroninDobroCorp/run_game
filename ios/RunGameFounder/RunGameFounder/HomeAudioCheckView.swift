import SwiftUI

struct HomeAudioCheckView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var audio = AudioController()
    @State private var playbackFinished = false
    @State private var lockScreenConfirmed = false
    @State private var controlsConfirmed = false
    @State private var noCriticalIncidentsConfirmed = false

    var body: some View {
        ScrollView {
            VStack(spacing: 26) {
                Spacer(minLength: 24)
                ZStack {
                    Circle()
                        .stroke(Color.white.opacity(0.08), lineWidth: 18)
                    Circle()
                        .trim(from: 0, to: progress)
                        .stroke(
                            AngularGradient(colors: [RunGameTheme.violet, RunGameTheme.electric], center: .center),
                            style: StrokeStyle(lineWidth: 18, lineCap: .round)
                        )
                        .rotationEffect(.degrees(-90))
                    VStack(spacing: 8) {
                        Image(systemName: "headphones")
                            .font(.system(size: 34, weight: .semibold))
                            .foregroundStyle(RunGameTheme.electric)
                        Text(Formatters.clock(audio.elapsed))
                            .font(.system(size: 42, weight: .black, design: .rounded).monospacedDigit())
                        Text("из \(Formatters.clock(audio.duration))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(width: 250, height: 250)

                VStack(spacing: 14) {
                    Text("Домашняя проверка master")
                        .font(.title2.bold())
                    Text("Запусти аудио, заблокируй экран и убедись, что реплики и NAV продолжают звучать. Проверка отметится автоматически после полного воспроизведения.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }

                Button {
                    if audio.isPlaying {
                        audio.pause()
                    } else {
                        let _: Bool = audio.play()
                    }
                } label: {
                    Label(audio.isPlaying ? "Пауза" : "Воспроизвести", systemImage: audio.isPlaying ? "pause.fill" : "play.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.violet)
                .accessibilityIdentifier("homeAudioPlayPause")

                VStack(alignment: .leading, spacing: 12) {
                    Text("После полного окончания").font(.headline)
                    Toggle("Экран был заблокирован", isOn: $lockScreenConfirmed)
                    Toggle("Pause/Play на lock screen работали", isOn: $controlsConfirmed)
                    Toggle("Не было остановок, пропусков или конфликтов", isOn: $noCriticalIncidentsConfirmed)
                    Button {
                        let record = AudioApprovalRecord(
                            schemaVersion: "0.2",
                            audioSHA256: mission.audioSHA256,
                            completedAt: Date(),
                            playbackDurationSeconds: audio.elapsed,
                            lockScreenConfirmed: lockScreenConfirmed,
                            controlsConfirmed: controlsConfirmed,
                            noCriticalIncidentsConfirmed: noCriticalIncidentsConfirmed
                        )
                        appModel.markHomeAudioCompleted(record: record)
                    } label: {
                        Label("Подтвердить домашнюю проверку", systemImage: "checkmark.shield")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(RunGameTheme.electric)
                    .foregroundStyle(RunGameTheme.ink)
                    .accessibilityIdentifier("homeAudioApprovalButton")
                    .disabled(!canApprove)
                }
                .runGamePanel()

                if appModel.homeAudioCompleted {
                    Label("Домашняя проверка завершена", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(RunGameTheme.electric)
                        .runGamePanel()
                }
                if let error = audio.errorMessage {
                    Text(error).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                if !audio.incidents.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Проверка не засчитана: начни новое полное прослушивание после устранения инцидента.")
                            .font(.footnote.bold())
                        ForEach(audio.incidents, id: \.occurredAt) { incident in
                            Text("• \(incident.message)").font(.caption)
                        }
                    }
                    .foregroundStyle(RunGameTheme.warning)
                    .runGamePanel()
                }
            }
            .padding(22)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Проверка аудио")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            audio.onFinished = { playbackFinished = true }
            audio.onStopRequested = {
                playbackFinished = false
                audio.stop()
            }
            audio.onFatalError = { _ in playbackFinished = false }
            audio.prepare(
                fileName: mission.audioFile,
                title: mission.title,
                expectedDuration: mission.durationSeconds
            )
        }
        .onDisappear { audio.stop() }
    }

    private var progress: Double {
        guard audio.duration > 0 else { return 0 }
        return min(1, audio.elapsed / audio.duration)
    }

    private var canApprove: Bool {
        playbackFinished
            && audio.elapsed >= mission.durationSeconds - 1
            && lockScreenConfirmed
            && controlsConfirmed
            && noCriticalIncidentsConfirmed
            && audio.incidents.isEmpty
            && !appModel.homeAudioCompleted
    }
}
