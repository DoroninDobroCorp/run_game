import SwiftUI

struct MissionRunView: View {
    private enum RunState { case ready, running, completed, aborted }

    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var audio = AudioController()
    @StateObject private var recorder = LocationRecorder()
    @State private var state: RunState = .ready
    @State private var showAbortConfirmation = false
    @State private var showDebrief = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                statusHeader
                timelineCard
                primaryControls
                safetyCard
                if let url = recorder.exportedURL {
                    ShareLink(item: url) {
                        Label("Экспортировать GPX этой сессии", systemImage: "square.and.arrow.up")
                    }
                    .runGamePanel()
                }
                if let error = audio.errorMessage ?? recorder.lastError {
                    Text(error).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
            }
            .padding(22)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("M1-A")
        .navigationBarTitleDisplayMode(.inline)
        .interactiveDismissDisabled(state == .running)
        .confirmationDialog("Остановить миссию?", isPresented: $showAbortConfirmation) {
            Button("Остановить и сохранить GPX", role: .destructive) { abort() }
            Button("Продолжить", role: .cancel) {}
        } message: {
            Text("Не компенсируй пропущенное ускорением. Остановка — корректный исход теста.")
        }
        .navigationDestination(isPresented: $showDebrief) {
            DebriefView(mission: mission, aborted: state == .aborted)
        }
        .onAppear {
            audio.prepare(fileName: mission.audioFile, title: mission.title)
            audio.onFinished = { finish() }
        }
        .onDisappear {
            if state != .running { audio.pause() }
        }
    }

    private var statusHeader: some View {
        VStack(spacing: 14) {
            ZStack {
                Circle()
                    .stroke(Color.white.opacity(0.08), lineWidth: 20)
                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(
                        state == .aborted ? RunGameTheme.danger : RunGameTheme.electric,
                        style: StrokeStyle(lineWidth: 20, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
                VStack(spacing: 5) {
                    Text(Formatters.clock(audio.elapsed))
                        .font(.system(size: 48, weight: .black, design: .rounded).monospacedDigit())
                    Text(stateLabel.uppercased())
                        .font(.caption2.bold())
                        .tracking(1.2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 270, height: 270)
            Text("Телефон можно заблокировать после старта. Аудио и GPS продолжат работу в фоне.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
    }

    private var timelineCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Сейчас").font(.caption.bold()).foregroundStyle(.secondary)
            Text(appModel.timelineBlock(at: audio.elapsed)?.label ?? (state == .completed ? "Миссия завершена" : "Подготовка"))
                .font(.title2.bold())
            HStack {
                Label("\(recorder.samples.count) GPS", systemImage: "location.fill")
                Spacer()
                Text("Осталось \(Formatters.clock(max(0, mission.durationSeconds - audio.elapsed)))")
            }
            .font(.caption.monospacedDigit())
            .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    @ViewBuilder
    private var primaryControls: some View {
        switch state {
        case .ready:
            Button(action: start) {
                Label("Начать миссию", systemImage: "play.fill")
                    .font(.title3.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .tint(RunGameTheme.electric)
            .foregroundStyle(RunGameTheme.ink)
        case .running:
            VStack(spacing: 12) {
                Button {
                    audio.isPlaying ? audio.pause() : audio.play()
                } label: {
                    Label(audio.isPlaying ? "Пауза" : "Продолжить", systemImage: audio.isPlaying ? "pause.fill" : "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.violet)
                Button("Аварийно остановить", role: .destructive) { showAbortConfirmation = true }
                    .frame(maxWidth: .infinity)
            }
        case .completed, .aborted:
            Button {
                showDebrief = true
            } label: {
                Label("Заполнить дебриф", systemImage: "square.and.pencil")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(RunGameTheme.violet)
        }
    }

    private var safetyCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("При конфликте с дорогой история всегда проигрывает", systemImage: "shield.fill")
                .font(.headline)
                .foregroundStyle(RunGameTheme.warning)
            Text("Не ускоряйся ради cue, не возвращайся к пропущенной точке и останови тест при боли, небезопасном переходе или необходимости смотреть в экран на ходу.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    private var progress: Double {
        guard mission.durationSeconds > 0 else { return 0 }
        return min(1, audio.elapsed / mission.durationSeconds)
    }

    private var stateLabel: String {
        switch state {
        case .ready: return "Готово к старту"
        case .running: return audio.isPlaying ? "Миссия идёт" : "Пауза"
        case .completed: return "Завершено"
        case .aborted: return "Остановлено"
        }
    }

    private func start() {
        recorder.start()
        audio.play()
        state = .running
    }

    private func finish() {
        recorder.stop(prefix: "m01-founder-run")
        state = .completed
    }

    private func abort() {
        audio.stop()
        recorder.stop(prefix: "m01-founder-aborted")
        state = .aborted
    }
}
