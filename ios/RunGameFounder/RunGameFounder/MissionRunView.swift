import CoreLocation
import SwiftUI

struct MissionRunView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var coordinator: SessionCoordinator
    @State private var showAbortConfirmation = false
    @State private var showDebrief = false

    @State private var familiarRouteConfirmed = false
    @State private var conditionsConfirmed = false
    @State private var surroundingsAudibleConfirmed = false
    @State private var readinessToStopConfirmed = false
    @State private var precommittedNextWorkout = Calendar.current.date(byAdding: .day, value: 2, to: Date()) ?? Date()

    init(mission: MissionConfig, appModel: AppModel) {
        self.mission = mission
        let initialWorkoutDate = Calendar.current.date(byAdding: .day, value: 2, to: Date()) ?? Date()
        _precommittedNextWorkout = State(initialValue: initialWorkoutDate)
        _coordinator = StateObject(wrappedValue: SessionCoordinator(
            mission: mission,
            appModel: appModel,
            precommittedNextWorkoutAt: initialWorkoutDate
        ))
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if appModel.evidenceCaptureLocked {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("Evidence Capture Locked", systemImage: "lock.fill")
                            .font(.headline)
                            .foregroundStyle(RunGameTheme.warning)
                        if let errorBanner = appModel.journalErrorBanner {
                            Text(errorBanner)
                                .font(.footnote)
                        } else if appModel.queueCorrupted {
                            Text("Очередь сессий повреждена. Захват evidence заблокирован.")
                                .font(.footnote)
                        } else if !appModel.pendingDebriefs.isEmpty {
                            Text("Присутствует незавершённый immediate-дебриф. Завершите его перед новым запуском.")
                                .font(.footnote)
                        } else if !appModel.pendingRecalls.isEmpty {
                            Text("Присутствует ожидающий 24-часовой recall. Новая миссия заблокирована.")
                                .font(.footnote)
                        } else if appModel.loadError != nil {
                            Text("Состояние приложения или bundle повреждено.")
                                .font(.footnote)
                        }
                    }
                    .runGamePanel()
                    .accessibilityIdentifier("evidenceLockBanner")
                }

                if !appModel.evidenceCaptureLocked {
                    statusHeader
                    timelineCard
                    if coordinator.isReady { preRunChecklist }
                    primaryControls
                    safetyCard
                }
                if let url = coordinator.recorder.exportedURL {
                    ShareLink(item: url) {
                        Label("Экспортировать GPX этой сессии", systemImage: "square.and.arrow.up")
                    }
                    .runGamePanel()
                }
                if let statusMessage = coordinator.statusMessage {
                    Text(statusMessage).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                if let error = coordinator.audio.errorMessage {
                    Text("Audio: \(error)").foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                if let error = coordinator.recorder.lastError {
                    Text("GPS: \(error)").foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
            }
            .padding(22)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("M1-A")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(coordinator.isRunning || coordinator.isAcquiringGPS)
        .interactiveDismissDisabled(coordinator.isRunning || coordinator.isAcquiringGPS)
        .confirmationDialog("Остановить миссию?", isPresented: $showAbortConfirmation) {
            Button("Остановить и сохранить partial GPX", role: .destructive) {
                coordinator.abortSession(reason: "Founder emergency stop from app UI")
            }
            Button("Продолжить", role: .cancel) {}
        } message: {
            Text("Не компенсируй пропущенное ускорением. Остановка — корректный исход теста.")
        }
        .navigationDestination(isPresented: $showDebrief) {
            if let context = coordinator.currentContext {
                DebriefView(mission: mission, context: context)
            }
        }
        .onDisappear {
            if coordinator.isRunning || coordinator.isAcquiringGPS {
                coordinator.abortSession(reason: "Mission screen was dismissed before evidence completion")
            } else {
                coordinator.audio.stop()
            }
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
                        coordinator.isAborted ? RunGameTheme.danger : RunGameTheme.electric,
                        style: StrokeStyle(lineWidth: 20, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
                VStack(spacing: 5) {
                    Text(Formatters.clock(coordinator.audio.elapsed))
                        .font(.system(size: 48, weight: .black, design: .rounded).monospacedDigit())
                    Text(stateLabel.uppercased())
                        .font(.caption2.bold())
                        .tracking(1.2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 270, height: 270)
            Text("Телефон можно заблокировать только после подтверждённого старта аудио и GPS.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
    }

    private var timelineCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Сейчас").font(.caption.bold()).foregroundStyle(.secondary)
            Text(appModel.timelineBlock(at: coordinator.audio.elapsed)?.label ?? (coordinator.isCompleted ? "Миссия завершена" : "Подготовка"))
                .font(.title2.bold())
            HStack {
                Label("\(coordinator.recorder.samples.count) GPS", systemImage: "location.fill")
                Spacer()
                Text("Осталось \(Formatters.clock(max(0, mission.durationSeconds - coordinator.audio.elapsed)))")
            }
            .font(.caption.monospacedDigit())
            .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    private var preRunChecklist: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Preflight этой попытки").font(.headline)
            Toggle("Маршрут знаком после дневного обхода", isOn: $familiarRouteConfirmed)
            Toggle("Свет, погода, трафик и самочувствие подходят", isOn: $conditionsConfirmed)
            Toggle("Громкость позволяет слышать окружение", isOn: $surroundingsAudibleConfirmed)
            Toggle("Я остановлю движение перед pause/экраном", isOn: $readinessToStopConfirmed)
            DatePicker(
                "Следующая тренировка заранее назначена",
                selection: $precommittedNextWorkout,
                displayedComponents: [.date, .hourAndMinute]
            )
            .onChange(of: precommittedNextWorkout) { _, newValue in
                coordinator.updatePrecommittedNextWorkoutAt(newValue)
            }
            Text("GPS дополнительно проверит свежую точную позицию не дальше 100 м от публичного старта.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    @ViewBuilder
    private var primaryControls: some View {
        switch coordinator.state {
        case .ready:
            Button(action: beginStart) {
                Label("Проверить GPS и начать", systemImage: "play.fill")
                    .font(.title3.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .tint(RunGameTheme.electric)
            .foregroundStyle(RunGameTheme.ink)
            .accessibilityIdentifier("startMissionButton")
            .accessibilityLabel("Проверить GPS и начать миссию")
            .disabled(!preflightComplete || !coordinator.audio.isPrepared || !appModel.canBeginMission || appModel.evidenceCaptureLocked)
        case .acquiringGPS:
            VStack(spacing: 12) {
                HStack {
                    ProgressView()
                    Text("Ищем свежую точную GPS-точку у старта…")
                }
                Button("Отменить запуск", role: .destructive) {
                    coordinator.send(.audioStartFailed(reason: "Запуск отменён до начала аудио."))
                }
                .accessibilityIdentifier("cancelGPSButton")
                .accessibilityLabel("Отменить запуск миссии")
            }
            .runGamePanel()
        case .running:
            VStack(spacing: 12) {
                Button {
                    if coordinator.audio.isPlaying {
                        coordinator.send(.pauseRequested)
                    } else {
                        coordinator.send(.resumeRequested)
                    }
                } label: {
                    Label(coordinator.audio.isPlaying ? "Пауза" : "Продолжить", systemImage: coordinator.audio.isPlaying ? "pause.fill" : "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.violet)
                .accessibilityIdentifier(coordinator.audio.isPlaying ? "pauseMissionButton" : "resumeMissionButton")
                .accessibilityLabel(coordinator.audio.isPlaying ? "Поставить миссию на паузу" : "Продолжить миссию")

                Button("Аварийно остановить", role: .destructive) { showAbortConfirmation = true }
                    .frame(maxWidth: .infinity)
                    .accessibilityIdentifier("abortMissionButton")
                    .accessibilityLabel("Аварийно остановить миссию")
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
            .accessibilityIdentifier("fillDebriefButton")
            .accessibilityLabel("Заполнить дебриф миссии")
            .disabled(coordinator.currentContext == nil)
        }
    }

    private var safetyCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("При конфликте с дорогой история всегда проигрывает", systemImage: "shield.fill")
                .font(.headline)
                .foregroundStyle(RunGameTheme.warning)
            Text("Не ускоряйся ради cue, не возвращайся к пропущенной точке. При боли, головокружении, небезопасном переходе или необходимости смотреть на экран сначала останови движение, затем приложение.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            Text("Эта fitness-сетка — личный research fixture и ещё не прошла профильный review; она не является медицинской или тренировочной рекомендацией.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    private var progress: Double {
        guard mission.durationSeconds > 0 else { return 0 }
        return min(1, coordinator.audio.elapsed / mission.durationSeconds)
    }

    private var preflightComplete: Bool {
        familiarRouteConfirmed
            && conditionsConfirmed
            && surroundingsAudibleConfirmed
            && readinessToStopConfirmed
            && precommittedNextWorkout > Date()
    }

    private var stateLabel: String {
        switch coordinator.state {
        case .ready: return "Готово к проверке"
        case .acquiringGPS: return "Проверка GPS"
        case .running: return coordinator.audio.isPlaying ? "Миссия идёт" : "Пауза"
        case .completed: return "Завершено"
        case .aborted: return "Остановлено"
        }
    }

    private func beginStart() {
        guard preflightComplete, coordinator.audio.isPrepared, appModel.canBeginMission, !appModel.evidenceCaptureLocked else { return }
        let runID = UUID().uuidString.lowercased()
        coordinator.send(.requestStart(runID: runID, now: Date()))
    }
}
