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
                hero
                readiness
                actionCards
                evidenceNotice
                resetButton
            }
            .padding(20)
            .padding(.bottom, 24)
        }
        .navigationTitle("Run Game")
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog("Сбросить локальные проверки?", isPresented: $showResetConfirmation) {
            Button("Сбросить", role: .destructive) { appModel.resetLocalApprovals() }
        } message: {
            Text("Маршрут и домашнее прослушивание снова будут отмечены как непроверенные.")
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
                Label("30 минут", systemImage: "timer")
                Label("8 интервалов", systemImage: "figure.run")
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
                Text("Готовность к миссии")
                    .font(.headline)
                Spacer()
                Text("\(appModel.readinessCompletedSteps)/3")
                    .font(.headline.monospacedDigit())
                    .foregroundStyle(RunGameTheme.electric)
            }
            ProgressView(value: Double(appModel.readinessCompletedSteps), total: 3)
                .tint(RunGameTheme.electric)
            readinessRow("Bundle загружен", complete: true)
            readinessRow("Маршрут пройден и одобрен", complete: appModel.routeApproved)
            readinessRow("Master прослушан дома", complete: appModel.homeAudioCompleted)
        }
        .runGamePanel()
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
                    complete: appModel.routeApproved
                )
            }
            .accessibilityIdentifier("routeWalkthroughLink")
            NavigationLink {
                HomeAudioCheckView(mission: mission)
            } label: {
                actionLabel(
                    number: "02",
                    title: "Прослушать дома",
                    detail: "Проверка lock-screen master без движения",
                    icon: "headphones",
                    complete: appModel.homeAudioCompleted
                )
            }
            .accessibilityIdentifier("homeAudioLink")
            NavigationLink {
                MissionRunView(mission: mission)
            } label: {
                actionLabel(
                    number: "03",
                    title: "Начать M1-A",
                    detail: appModel.canStartMission ? "Founder run готов к запуску" : "Откроется после шагов 01 и 02",
                    icon: "figure.run.circle.fill",
                    complete: false,
                    locked: !appModel.canStartMission
                )
            }
            .accessibilityIdentifier("missionRunLink")
            .disabled(!appModel.canStartMission)
        }
        .buttonStyle(.plain)
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
