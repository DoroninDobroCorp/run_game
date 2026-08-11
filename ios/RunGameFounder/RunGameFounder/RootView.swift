import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appModel: AppModel

    var body: some View {
        NavigationStack {
            Group {
                if let mission = appModel.mission {
                    DashboardView(mission: mission)
                } else {
                    ContentUnavailableView(
                        "Миссия не подготовлена",
                        systemImage: "exclamationmark.triangle.fill",
                        description: Text(appModel.loadError ?? "Неизвестная ошибка локального bundle")
                    )
                }
            }
            .background(RunGameTheme.ink.ignoresSafeArea())
        }
        .tint(RunGameTheme.electric)
    }
}

private struct DashboardView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @State private var showResetConfirmation = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                recoveryErrorBanner
                hero
                readiness
                debriefQueue
                recallQueue
                recoveredTracks
                localEvidence
                actionCards
                evidenceNotice
                resetButton
            }
            .padding(20)
            .padding(.bottom, 24)
        }
        .navigationTitle("Run Game")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { appModel.refreshRecoveredTracks() }
        .confirmationDialog("Сбросить локальные проверки?", isPresented: $showResetConfirmation) {
            Button("Сбросить", role: .destructive) { appModel.resetLocalApprovals() }
        } message: {
            Text("Маршрут и домашнее прослушивание снова будут отмечены как непроверенные.")
        }
    }

    @ViewBuilder
    private var recoveryErrorBanner: some View {
        if appModel.journalCorrupted || appModel.queueCorrupted {
            VStack(alignment: .leading, spacing: 8) {
                Label("Recovery Error / Evidence Locked", systemImage: "exclamationmark.triangle.fill")
                    .font(.headline)
                    .foregroundStyle(RunGameTheme.warning)
                Text(appModel.journalErrorBanner ?? "Очередь сессий или журнал активности повреждены. Захват evidence заблокирован.")
                    .font(.footnote)
                if appModel.journalCorrupted {
                    Button("Сбросить карантин журнала", role: .destructive) {
                        appModel.resetJournalQuarantine()
                    }
                    .font(.caption.bold())
                    .accessibilityIdentifier("resetQuarantineButton")
                }
            }
            .runGamePanel()
            .accessibilityIdentifier("recoveryErrorBanner")
        }
    }

    @ViewBuilder
    private var localEvidence: some View {
        if !appModel.localEvidenceURLs.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Label("Локальные evidence-файлы", systemImage: "externaldrive.fill")
                    .font(.headline)
                Text("Индекс Documents для повторного экспорта после перезапуска; отправка происходит только по нажатию Share.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                ForEach(appModel.localEvidenceURLs, id: \.self) { url in
                    ShareLink(item: url) {
                        Label(url.lastPathComponent, systemImage: "square.and.arrow.up")
                            .font(.caption.monospaced())
                    }
                }
            }
            .runGamePanel()
        }
    }

    @ViewBuilder
    private var debriefQueue: some View {
        if !appModel.pendingDebriefs.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label("Незавершённый immediate-дебриф", systemImage: "square.and.pencil")
                    .font(.headline)
                    .foregroundStyle(RunGameTheme.warning)
                Text("Контекст попытки сохранён локально. Заверши evidence до обсуждения истории или правок.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                ForEach(appModel.pendingDebriefs, id: \.runID) { context in
                    NavigationLink {
                        DebriefView(mission: mission, context: context)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(context.runID).font(.caption.monospaced())
                                Text(context.aborted ? "Aborted evidence" : "Immediate evidence")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                        }
                    }
                }
            }
            .runGamePanel()
        }
    }

    @ViewBuilder
    private var recallQueue: some View {
        if !appModel.pendingRecalls.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label("24-часовой recall", systemImage: "brain.head.profile")
                    .font(.headline)
                Text("Заполняется без просмотра immediate JSON; исходные evidence-файлы не перезаписываются.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                ForEach(appModel.pendingRecalls) { record in
                    NavigationLink {
                        RecallView(record: record)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(record.runID).font(.caption.monospaced())
                                Text(Date() >= record.dueAt ? "Окно открыто" : "Откроется через 24 часа")
                                    .font(.caption2)
                                    .foregroundStyle(Date() >= record.dueAt ? RunGameTheme.electric : .secondary)
                            }
                            Spacer()
                            Image(systemName: Date() >= record.dueAt ? "chevron.right" : "lock.fill")
                        }
                    }
                }
            }
            .runGamePanel()
        }
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(mission.subtitle.uppercased())
                .font(.caption.weight(.bold))
                .tracking(1.4)
                .foregroundStyle(RunGameTheme.electric)
            Text(mission.title)
                .font(.system(size: 38, weight: .black, design: .rounded))
            Text(mission.locationDisplayName)
                .font(.title3.weight(.semibold))
                .foregroundStyle(.secondary)
            HStack(spacing: 10) {
                Label("\(Int(mission.durationSeconds / 60)) минут", systemImage: "timer")
                Label("\(mission.timeline.filter { $0.kind == "run" }.count) интервалов", systemImage: "figure.run")
                Label("офлайн-аудио", systemImage: "airplane")
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 8)
    }

    private var readiness: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Готовность устройства")
                    .font(.headline)
                Spacer()
                Text("\(appModel.readinessCompletedSteps)/3")
                    .font(.headline.monospacedDigit())
                    .foregroundStyle(RunGameTheme.electric)
            }
            ProgressView(value: Double(appModel.readinessCompletedSteps), total: 3)
                .tint(RunGameTheme.electric)
            readinessRow("Bundle и SHA master проверены", complete: true)
            readinessRow("Маршрут записан GPX и одобрен", complete: appModel.routeApproved)
            readinessRow("Master полностью проверен дома", complete: appModel.homeAudioCompleted)
            Divider()
            readinessRow("Отдельный Mac gate: field review в binding", complete: mission.m1HumanApprovalComplete)
        }
        .runGamePanel()
    }

    @ViewBuilder
    private var recoveredTracks: some View {
        if !appModel.recoveredTrackURLs.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Label("Найдена незавершённая GPS-сессия", systemImage: "exclamationmark.arrow.triangle.2.circlepath")
                    .font(.headline)
                    .foregroundStyle(RunGameTheme.warning)
                Text("Приложение не считает её завершённой. Экспортируй recovery GPX как aborted evidence до нового запуска.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                ForEach(appModel.recoveredTrackURLs, id: \.self) { url in
                    ShareLink(item: url) {
                        Label("Экспортировать \(url.lastPathComponent)", systemImage: "square.and.arrow.up")
                            .font(.caption)
                    }
                }
            }
            .runGamePanel()
        }
    }

    private var actionCards: some View {
        VStack(spacing: 14) {
            NavigationLink {
                RouteWalkthroughView(mission: mission)
            } label: {
                actionLabel(
                    number: "01",
                    title: "Проверить маршрут",
                    detail: "Карта, дневной обход и локальный GPX",
                    icon: "map.fill",
                    complete: appModel.routeApproved,
                    locked: appModel.evidenceCaptureLocked
                )
            }
            .accessibilityIdentifier("routeWalkthroughLink")
            .disabled(appModel.evidenceCaptureLocked)
            NavigationLink {
                HomeAudioCheckView(mission: mission)
            } label: {
                actionLabel(
                    number: "02",
                    title: "Прослушать дома",
                    detail: "Проверка lock-screen master без движения",
                    icon: "headphones",
                    complete: appModel.homeAudioCompleted,
                    locked: appModel.evidenceCaptureLocked
                )
            }
            .accessibilityIdentifier("homeAudioLink")
            .disabled(appModel.evidenceCaptureLocked)
            NavigationLink {
                MissionRunView(mission: mission, appModel: appModel)
            } label: {
                actionLabel(
                    number: "03",
                    title: "Начать M1-A",
                    detail: missionStartDetail,
                    icon: "figure.run.circle.fill",
                    complete: false,
                    locked: !appModel.canBeginMission || appModel.evidenceCaptureLocked
                )
            }
            .accessibilityIdentifier("missionRunLink")
            .disabled(!appModel.canBeginMission || appModel.evidenceCaptureLocked)
        }
    }

    private var missionStartDetail: String {
        if !appModel.pendingDebriefs.isEmpty {
            return "Сначала заверши незавершённый immediate-дебриф"
        }
        if !appModel.pendingRecalls.isEmpty {
            return "Новая M1 откроется после обязательного 24-часового recall"
        }
        if appModel.canStartMission {
            return "Founder run готов к запуску"
        }
        return mission.m1HumanApprovalComplete
            ? "Откроется после шагов 01 и 02"
            : "Сначала закрой human_blockers_to_m1_a на Mac"
    }

    private var evidenceNotice: some View {
        Label(mission.evidenceNotice, systemImage: "shield.lefthalf.filled")
            .font(.footnote)
            .foregroundStyle(.secondary)
            .runGamePanel()
    }

    private var resetButton: some View {
        Button("Сбросить локальную готовность", role: .destructive) {
            showResetConfirmation = true
        }
        .font(.footnote)
        .frame(maxWidth: .infinity)
    }

    private func readinessRow(_ text: String, complete: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: complete ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(complete ? RunGameTheme.electric : .secondary)
            Text(text)
                .foregroundStyle(complete ? .primary : .secondary)
            Spacer()
        }
        .font(.subheadline.weight(.medium))
    }

    private func actionLabel(
        number: String,
        title: String,
        detail: String,
        icon: String,
        complete: Bool,
        locked: Bool = false
    ) -> some View {
        HStack(spacing: 16) {
            VStack {
                Text(number)
                    .font(.caption2.weight(.black))
                    .foregroundStyle(RunGameTheme.ink)
            }
            .frame(width: 38, height: 38)
            .background(complete ? RunGameTheme.electric : (locked ? Color.secondary : RunGameTheme.violet), in: Circle())
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: complete ? "checkmark" : (locked ? "lock.fill" : icon))
                .foregroundStyle(complete ? RunGameTheme.electric : .secondary)
        }
        .runGamePanel()
    }
}
