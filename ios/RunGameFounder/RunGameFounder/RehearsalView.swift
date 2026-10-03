import SwiftUI

struct RehearsalView: View {
    @ObservedObject var rehearsal: Rehearsal
    @State private var speed = 30.0
    @State private var lastTick: TimeInterval?
    @State private var showDiscardConfirmation = false
    @Environment(\.scenePhase) private var scenePhase
    private let timer = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Label("СИМУЛЯЦИЯ · БЕЗ ДВИЖЕНИЯ", systemImage: "play.desktopcomputer")
                    .font(.caption.bold()).tracking(1).foregroundStyle(RunGameTheme.electric)
                Text(rehearsal.mission.locationDisplayName).font(.largeTitle.bold())
                Text("Посмотри, как пройдёт миссия: маршрут, восемь беговых интервалов и возвращение к старту.")
                    .foregroundStyle(.secondary)
                if let route = rehearsal.mission.offlineRoute {
                    RouteDiagram(route: route, progress: rehearsal.routeProgress).frame(height: 290)
                    HStack {
                        Label(String(format: "%.2f км", route.distanceMeters / 1000), systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                        Spacer()
                        Label("30 минут", systemImage: "clock")
                    }.font(.subheadline.weight(.semibold))
                }
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(Formatters.clock(rehearsal.elapsed)).font(.system(size: 46, weight: .bold, design: .rounded).monospacedDigit())
                            .accessibilityIdentifier("rehearsalClock")
                        Spacer()
                        Text("/ 30:00").foregroundStyle(.secondary)
                    }
                    Text(rehearsal.currentBlock?.label ?? (rehearsal.report != nil ? "Круг завершён" : "Подготовка"))
                        .font(.title3.bold()).foregroundStyle(RunGameTheme.electric)
                    ProgressView(value: rehearsal.progress).tint(RunGameTheme.electric)
                    if let block = rehearsal.currentBlock {
                        Text("До смены интервала \(Formatters.clock(block.end - rehearsal.elapsed))")
                            .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    }
                }.runGamePanel()
                if let report = rehearsal.report {
                    VStack(alignment: .leading, spacing: 12) {
                        Label(report.sessionCompleted ? "Тестовый круг пройден" : "Тест выявил проблему", systemImage: report.sessionCompleted ? "checkmark.circle.fill" : "exclamationmark.triangle")
                            .font(.title3.bold()).foregroundStyle(report.sessionCompleted ? RunGameTheme.electric : RunGameTheme.warning)
                            .accessibilityIdentifier("rehearsalResult")
                        Text("\(report.visitedWaypoints)/\(report.totalWaypoints) точек с финишем · \(report.intervalsCompleted) интервалов · \(report.sampleCount) виртуальных GPS-точек")
                            .font(.subheadline)
                        if let url = rehearsal.reportURL {
                            ShareLink(item: url) { Label("Сохранить результат теста", systemImage: "square.and.arrow.up") }
                        } else {
                            Button("Сохранить результат теста") { rehearsal.saveReport() }
                        }
                        Button("Пройти ещё раз") {
                            if rehearsal.hasUnsavedReport { showDiscardConfirmation = true }
                            else { rehearsal.reset(); lastTick = nil }
                        }
                            .accessibilityIdentifier("rehearsalReset")
                    }.runGamePanel()
                } else {
                    Picker("Скорость симуляции", selection: $speed) {
                        Text("1×").tag(1.0); Text("30× · 1 мин").tag(30.0); Text("120× · 15 с").tag(120.0)
                    }.pickerStyle(.segmented).accessibilityIdentifier("rehearsalSpeed")
                    Button {
                        if rehearsal.isPlaying { rehearsal.pause() }
                        else { rehearsal.play() }
                        lastTick = ProcessInfo.processInfo.systemUptime
                    } label: {
                        Label(rehearsal.isPlaying ? "Пауза" : (rehearsal.elapsed == 0 ? "Начать тестовый круг" : "Продолжить"), systemImage: rehearsal.isPlaying ? "pause.fill" : "play.fill")
                            .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 12)
                    }.buttonStyle(.borderedProminent).tint(RunGameTheme.electric).foregroundStyle(RunGameTheme.ink)
                        .accessibilityIdentifier("rehearsalPlayPause")
                }
                if let error = rehearsal.errorMessage {
                    Text(error).foregroundStyle(RunGameTheme.warning).runGamePanel()
                }
                Text("Положение и время здесь виртуальные. Аудио проверь отдельно в «Прослушать дома». Симуляция не записывает твой GPS, не подтверждает маршрут и не создаёт исследовательский забег.")
                    .font(.footnote).foregroundStyle(.secondary)
                if let route = rehearsal.mission.offlineRoute {
                    Text(route.attribution).font(.caption2).foregroundStyle(.secondary)
                }
            }.padding(20)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Тестовый забег")
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog("Начать заново без сохранения?", isPresented: $showDiscardConfirmation) {
            Button("Начать заново", role: .destructive) { rehearsal.reset(); lastTick = nil }
        } message: {
            Text("Результат этого тестового круга ещё не сохранён. При новом старте он будет удалён.")
        }
        .onReceive(timer) { _ in
            let now = ProcessInfo.processInfo.systemUptime
            defer { lastTick = now }
            guard let lastTick, rehearsal.isPlaying else { return }
            rehearsal.advance(by: min(1, max(0, now - lastTick)) * speed)
            if rehearsal.report != nil { rehearsal.saveReport() }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { rehearsal.pause(); lastTick = nil }
        }
        .onDisappear { rehearsal.pause() }
    }
}
