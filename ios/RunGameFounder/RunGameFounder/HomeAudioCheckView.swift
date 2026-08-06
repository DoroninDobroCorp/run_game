import SwiftUI

struct HomeAudioCheckView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var audio = AudioController()

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
                    audio.isPlaying ? audio.pause() : audio.play()
                } label: {
                    Label(audio.isPlaying ? "Пауза" : "Воспроизвести", systemImage: audio.isPlaying ? "pause.fill" : "play.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.violet)
                .accessibilityIdentifier("homeAudioPlayPause")

                if appModel.homeAudioCompleted {
                    Label("Домашняя проверка завершена", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(RunGameTheme.electric)
                        .runGamePanel()
                }
                if let error = audio.errorMessage {
                    Text(error).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
            }
            .padding(22)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Проверка аудио")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            audio.prepare(fileName: mission.audioFile, title: mission.title)
            audio.onFinished = { appModel.markHomeAudioCompleted() }
        }
        .onDisappear { audio.pause() }
    }

    private var progress: Double {
        guard audio.duration > 0 else { return 0 }
        return min(1, audio.elapsed / audio.duration)
    }
}
