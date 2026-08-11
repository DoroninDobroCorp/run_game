import CoreLocation
import SwiftUI

struct MissionRunView: View {
    private enum RunState { case ready, acquiringGPS, running, completed, aborted }

    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var audio = AudioController()
    @StateObject private var recorder = LocationRecorder()
    @State private var state: RunState = .ready
    @State private var showAbortConfirmation = false
    @State private var showDebrief = false
    @State private var context: RunSessionContext?
    @State private var runID = UUID().uuidString.lowercased()
    @State private var runStartedAt: Date?
    @State private var qualifyingStartFixes = 0
    @State private var startMessage: String?
    @State private var firstFixTimeout: Task<Void, Never>?

    @State private var familiarRouteConfirmed = false
    @State private var conditionsConfirmed = false
    @State private var surroundingsAudibleConfirmed = false
    @State private var readinessToStopConfirmed = false
    @State private var precommittedNextWorkout = Calendar.current.date(byAdding: .day, value: 2, to: Date()) ?? Date()

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

                statusHeader
                timelineCard
                if state == .ready { preRunChecklist }
                primaryControls
                safetyCard
                if let url = recorder.exportedURL {
                    ShareLink(item: url) {
                        Label("Экспортировать GPX этой сессии", systemImage: "square.and.arrow.up")
                    }
                    .runGamePanel()
                }
                if let startMessage {
                    Text(startMessage).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                if let error = audio.errorMessage {
                    Text("Audio: \(error)").foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                if let error = recorder.lastError {
                    Text("GPS: \(error)").foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
            }
            .padding(22)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("M1-A")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(state == .running || state == .acquiringGPS)
        .interactiveDismissDisabled(state == .running || state == .acquiringGPS)
        .confirmationDialog("Остановить миссию?", isPresented: $showAbortConfirmation) {
            Button("Остановить и сохранить partial GPX", role: .destructive) {
                abort(reason: "Founder emergency stop from app UI")
            }
            Button("Продолжить", role: .cancel) {}
        } message: {
            Text("Не компенсируй пропущенное ускорением. Остановка — корректный исход теста.")
        }
        .navigationDestination(isPresented: $showDebrief) {
            if let context {
                DebriefView(mission: mission, context: context)
            }
        }
        .onAppear(perform: prepareSession)
        .onDisappear {
            if state == .running || state == .acquiringGPS {
                abort(reason: "Mission screen was dismissed before evidence completion")
            } else {
                audio.stop()
            }
            firstFixTimeout?.cancel()
        }
        .onChange(of: recorder.latestSample?.id) { _, _ in evaluateFirstFix() }
        .onChange(of: recorder.lastError) { _, newValue in
            if state == .acquiringGPS, let newValue {
                rollbackStart(reason: newValue)
            } else if state == .running, let newValue {
                abort(reason: "GPS session failed: \(newValue)")
            }
        }
        .onChange(of: audio.incidents.count) { _, _ in
            guard state == .running, let incident = audio.incidents.last else { return }
            switch incident.kind {
            case .interruptionBegan, .outputRouteDisconnected:
                abort(reason: "Audio session interrupted: \(incident.message)")
            default:
                break
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
            Text("Телефон можно заблокировать только после подтверждённого старта аудио и GPS.")
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
            Text("GPS дополнительно проверит свежую точную позицию не дальше 100 м от публичного старта.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    @ViewBuilder
    private var primaryControls: some View {
        switch state {
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
            .disabled(!preflightComplete || !audio.isPrepared || !appModel.canBeginMission || appModel.evidenceCaptureLocked)
        case .acquiringGPS:
            VStack(spacing: 12) {
                HStack {
                    ProgressView()
                    Text("Ищем свежую точную GPS-точку у старта…")
                }
                Button("Отменить запуск", role: .destructive) {
                    rollbackStart(reason: "Запуск отменён до начала аудио.")
                }
                .accessibilityIdentifier("cancelGPSButton")
                .accessibilityLabel("Отменить запуск миссии")
            }
            .runGamePanel()
        case .running:
            VStack(spacing: 12) {
                Button {
                    if audio.isPlaying {
                        audio.pause()
                    } else {
                        let started: Bool = audio.play()
                        if !started { abort(reason: "Audio could not resume") }
                    }
                } label: {
                    Label(audio.isPlaying ? "Пауза" : "Продолжить", systemImage: audio.isPlaying ? "pause.fill" : "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.violet)
                .accessibilityIdentifier(audio.isPlaying ? "pauseMissionButton" : "resumeMissionButton")
                .accessibilityLabel(audio.isPlaying ? "Поставить миссию на паузу" : "Продолжить миссию")

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
            .disabled(context == nil)
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
        return min(1, audio.elapsed / mission.durationSeconds)
    }

    private var preflightComplete: Bool {
        familiarRouteConfirmed
            && conditionsConfirmed
            && surroundingsAudibleConfirmed
            && readinessToStopConfirmed
            && precommittedNextWorkout > Date()
    }

    private var stateLabel: String {
        switch state {
        case .ready: return "Готово к проверке"
        case .acquiringGPS: return "Проверка GPS"
        case .running: return audio.isPlaying ? "Миссия идёт" : "Пауза"
        case .completed: return "Завершено"
        case .aborted: return "Остановлено"
        }
    }

    private func prepareSession() {
        audio.onFinished = { finish() }
        audio.onStopRequested = { abort(reason: "Remote stop from lock-screen controls") }
        audio.onFatalError = { message in
            if state == .running || state == .acquiringGPS {
                abort(reason: "Fatal audio error: \(message)")
            } else {
                startMessage = message
            }
        }
        audio.prepare(
            fileName: mission.audioFile,
            title: mission.title,
            expectedDuration: mission.durationSeconds
        )
    }

    private func beginStart() {
        guard preflightComplete, audio.isPrepared, appModel.canBeginMission, !appModel.evidenceCaptureLocked else { return }
        startMessage = nil
        context = nil
        runID = UUID().uuidString.lowercased()
        runStartedAt = nil
        qualifyingStartFixes = 0
        state = .acquiringGPS
        appModel.saveActiveAttempt(
            ActiveRunAttempt(
                runID: runID,
                missionID: mission.missionID,
                bindingID: mission.bindingID,
                audioSHA256: mission.audioSHA256,
                routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                condition: "A",
                phase: .acquiringGPS,
                startedAt: Date(),
                precommittedNextWorkoutAt: precommittedNextWorkout,
                pauseCount: 0,
                audioIncidents: [],
                locationIncidents: []
            )
        )
        let result = recorder.start(prefix: "\(mission.gpxPrefix)-run-\(runID)")
        if case .unavailable(let message) = result {
            rollbackStart(reason: message)
            return
        }
        firstFixTimeout?.cancel()
        firstFixTimeout = Task { @MainActor in
            try? await Task.sleep(for: .seconds(30))
            guard !Task.isCancelled, state == .acquiringGPS else { return }
            rollbackStart(reason: "За 30 секунд не получена точная GPS-точка у публичного старта.")
        }
    }

    private func evaluateFirstFix() {
        guard state == .acquiringGPS, let sample = recorder.latestSample,
              let start = mission.routePoints.first else { return }
        guard sample.horizontalAccuracy <= 35 else {
            qualifyingStartFixes = 0
            startMessage = "GPS accuracy пока ±\(Int(sample.horizontalAccuracy)) м; ждём значение ≤35 м."
            return
        }
        let distance = sample.location.distance(from: start.location)
        guard distance <= 100 else {
            qualifyingStartFixes = 0
            startMessage = "Текущая позиция примерно в \(Int(distance)) м от публичного старта. Подойди к старту; аудио ещё не запущено."
            return
        }

        qualifyingStartFixes += 1
        guard qualifyingStartFixes >= 2 else {
            startMessage = "Получена 1 из 2 последовательных точных GPS-точек у старта…"
            return
        }

        firstFixTimeout?.cancel()
        runStartedAt = Date()
        let started: Bool = audio.play()
        guard started else {
            rollbackStart(reason: audio.errorMessage ?? "Master-аудио не запустилось.")
            return
        }
        startMessage = nil
        state = .running
        appModel.saveActiveAttempt(
            ActiveRunAttempt(
                runID: runID,
                missionID: mission.missionID,
                bindingID: mission.bindingID,
                audioSHA256: mission.audioSHA256,
                routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                condition: "A",
                phase: .running,
                startedAt: runStartedAt ?? Date(),
                precommittedNextWorkoutAt: precommittedNextWorkout,
                pauseCount: audio.pauseCount,
                audioIncidents: audio.incidents.map { "\($0.kind.rawValue) @ \(Formatters.clock($0.elapsed)): \($0.message)" },
                locationIncidents: recorder.incidents
            )
        )
    }

    private func finish() {
        guard state == .running else { return }
        firstFixTimeout?.cancel()
        let summary = recorder.stop(completed: true)
        let routeTraversal = summary.map {
            WalkthroughEvidence.make(
                mission: mission,
                summary: $0,
                samples: recorder.samples,
                locationIncidents: recorder.incidents
            )
        }
        let successful = summary?.isSufficientMissionEvidence(for: mission) == true
            && routeTraversal?.isSufficient(for: mission) == true
            && audio.incidents.isEmpty
            && recorder.incidents.isEmpty
        var failureReasons: [String] = []
        if summary?.isSufficientMissionEvidence(for: mission) != true {
            failureReasons.append("GPX is missing or too short for the full mission")
        }
        if routeTraversal?.isSufficient(for: mission) != true {
            failureReasons.append("ordered route traversal or public start/finish evidence is incomplete")
        }
        if !audio.incidents.isEmpty { failureReasons.append("audio incident recorded") }
        if !recorder.incidents.isEmpty { failureReasons.append("location incident recorded") }
        let finishedContext = makeContext(
            completed: successful,
            aborted: !successful,
            abortReason: successful ? "" : failureReasons.joined(separator: "; "),
            elapsed: audio.elapsed,
            track: summary,
            routeTraversalEvidence: routeTraversal
        )
        context = finishedContext
        appModel.scheduleDebrief(for: finishedContext)
        appModel.clearActiveJournal()
        if successful {
            appModel.scheduleRecall(for: finishedContext)
        }
        state = successful ? .completed : .aborted
        appModel.refreshRecoveredTracks()
    }

    private func abort(reason: String) {
        guard state == .running || state == .acquiringGPS else { return }
        firstFixTimeout?.cancel()
        let elapsed = audio.elapsed
        audio.stop()
        let summary = recorder.stop(completed: false)
        let routeTraversal = summary.map {
            WalkthroughEvidence.make(
                mission: mission,
                summary: $0,
                samples: recorder.samples,
                locationIncidents: recorder.incidents
            )
        }
        let abortedContext = makeContext(
            completed: false,
            aborted: true,
            abortReason: reason,
            elapsed: elapsed,
            track: summary,
            routeTraversalEvidence: routeTraversal
        )
        context = abortedContext
        appModel.scheduleDebrief(for: abortedContext)
        appModel.clearActiveJournal()
        state = .aborted
        startMessage = reason
        appModel.refreshRecoveredTracks()
    }

    private func rollbackStart(reason: String) {
        guard state == .acquiringGPS else { return }
        firstFixTimeout?.cancel()
        recorder.cancelPendingStart()
        if recorder.isRecording { _ = recorder.stop(completed: false) }
        if audio.isPlaying { audio.stop() }
        appModel.clearActiveJournal()
        state = .ready
        startMessage = reason
        appModel.refreshRecoveredTracks()
    }

    private func makeContext(
        completed: Bool,
        aborted: Bool,
        abortReason: String,
        elapsed: TimeInterval,
        track: TrackSummary?,
        routeTraversalEvidence: WalkthroughEvidence?
    ) -> RunSessionContext {
        RunSessionContext(
            runID: runID,
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: runStartedAt ?? Date(),
            endedAt: Date(),
            precommittedNextWorkoutAt: precommittedNextWorkout,
            completed: completed,
            aborted: aborted,
            abortReason: abortReason,
            audioElapsedSeconds: elapsed,
            pauseCount: audio.pauseCount,
            track: track,
            routeTraversalEvidence: routeTraversalEvidence,
            audioIncidents: audio.incidents.map { "\($0.kind.rawValue) @ \(Formatters.clock($0.elapsed)): \($0.message)" },
            locationIncidents: recorder.incidents
        )
    }
}
