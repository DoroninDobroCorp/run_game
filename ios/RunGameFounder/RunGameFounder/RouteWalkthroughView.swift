import MapKit
import SwiftUI
import UIKit

struct RouteWalkthroughView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var planner = RoutePlanner()
    @StateObject private var recorder = LocationRecorder()
    @State private var cameraPosition: MapCameraPosition
    @State private var walkthroughEvidence: WalkthroughEvidence?
    @State private var showStopConfirmation = false

    init(mission: MissionConfig) {
        self.mission = mission
        _cameraPosition = State(initialValue: .region(Self.region(for: mission.routePoints)))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if appModel.evidenceCaptureLocked {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("Evidence Capture Locked", systemImage: "lock.fill")
                            .font(.headline)
                            .foregroundStyle(RunGameTheme.warning)
                        Text("Запись дневного обхода заблокирована до очистки pending-очередей.")
                            .font(.footnote)
                    }
                    .runGamePanel()
                    .accessibilityIdentifier("walkthroughLockBanner")
                }

                map
                routeSummary
                points
                recording
                approvalChecklist
            }
            .padding(18)
        }
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Дневной обход")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(recorder.isRecording || recorder.isAwaitingAuthorization)
        .confirmationDialog("Остановить дневной обход?", isPresented: $showStopConfirmation) {
            Button("Остановить и сохранить GPX", role: .destructive) { finishWalkthrough() }
            Button("Продолжить", role: .cancel) {}
        }
        .task { await planner.load(points: mission.routePoints) }
        .onAppear {
            if walkthroughEvidence == nil && !appModel.routeApproved {
                walkthroughEvidence = appModel.pendingWalkthroughEvidence
            }
        }
        .onDisappear {
            if recorder.isRecording {
                _ = recorder.stop(completed: false)
                appModel.refreshRecoveredTracks()
            } else if recorder.isAwaitingAuthorization {
                recorder.cancelPendingStart()
            }
        }
    }

    private var map: some View {
        Map(position: $cameraPosition) {
            ForEach(Array(mission.routePoints.enumerated()), id: \.element.id) { index, point in
                Marker(index == 0 ? "Старт" : point.name, coordinate: point.coordinate)
                    .tint(index == 0 ? RunGameTheme.electric : RunGameTheme.violet)
            }
            ForEach(Array(planner.polylines.enumerated()), id: \.offset) { _, polyline in
                MapPolyline(polyline)
                    .stroke(RunGameTheme.electric, lineWidth: 5)
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .frame(height: 360)
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .overlay(alignment: .topTrailing) {
            if planner.isLoading {
                ProgressView().padding(14).background(.ultraThinMaterial, in: Circle())
                    .padding(12)
            }
        }
    }

    private var routeSummary: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Пешеходный preview Apple Maps")
                .font(.headline)
            if let error = planner.errorMessage {
                Label(error, systemImage: "wifi.exclamationmark")
                    .font(.footnote)
                    .foregroundStyle(RunGameTheme.warning)
            } else if planner.isComplete {
                Text("Все \(planner.completedLegs) сегмента · ≈ \(planner.distanceMeters / 1000, specifier: "%.1f") км · обычная ходьба ≈ \(Int(planner.expectedTravelTime / 60)) мин")
                    .foregroundStyle(.secondary)
            } else {
                Text("Маршрут рассчитывается. Это preview, а не safety approval.")
                    .foregroundStyle(.secondary)
            }
        }
        .runGamePanel()
    }

    private var points: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Контрольные точки").font(.headline)
            ForEach(Array(mission.routePoints.dropLast().enumerated()), id: \.element.id) { index, point in
                Link(destination: point.osmURL) {
                    HStack(spacing: 12) {
                        Text("\(index + 1)")
                            .font(.caption.bold())
                            .frame(width: 28, height: 28)
                            .background(RunGameTheme.violet.opacity(0.25), in: Circle())
                        VStack(alignment: .leading) {
                            Text(point.name).foregroundStyle(.primary)
                            Text(point.roleLabel).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "arrow.up.right")
                    }
                }
            }
        }
        .runGamePanel()
    }

    private var recording: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Локальная запись GPX").font(.headline)
            Text("Трек остаётся в Documents приложения и никуда не отправляется автоматически.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            if recorder.isRecording {
                HStack {
                    ProgressView().tint(RunGameTheme.danger)
                    Text(recorder.samples.isEmpty ? "Ищем точный GPS…" : "Запись · \(recorder.samples.count) точек")
                        .font(.subheadline.monospacedDigit())
                }
                Button("Завершить обход и сохранить GPX", role: .destructive) {
                    showStopConfirmation = true
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.danger)
            } else if recorder.isAwaitingAuthorization {
                HStack {
                    ProgressView()
                    Text("Ожидаем разрешение точной геопозиции…")
                }
                Button("Отменить") { recorder.cancelPendingStart() }
            } else {
                Button {
                    walkthroughEvidence = nil
                    _ = recorder.start(prefix: "\(mission.gpxPrefix)-walkthrough")
                } label: {
                    Label("Начать дневной обход", systemImage: "location.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.electric)
                .disabled(!planner.isComplete || appModel.routeApproved || appModel.evidenceCaptureLocked)
            }
            if let url = recorder.exportedURL {
                ShareLink(item: url) {
                    Label("Экспортировать GPX", systemImage: "square.and.arrow.up")
                }
            }
            if let evidence = walkthroughEvidence {
                let expected = mission.routePoints.count
                VStack(alignment: .leading, spacing: 5) {
                    Text("Evidence: \(evidence.track.sampleCount) GPS · \(evidence.track.distanceMeters / 1000, specifier: "%.2f") км · \(Int(evidence.track.durationSeconds / 60)) мин")
                    Text("Максимальный разрыв GPS: \(Int(evidence.track.maximumSampleGapSeconds)) с (нужно ≤\(Int(TrackSummary.maximumEvidenceSampleGapSeconds)) с)")
                    Text("Контрольные точки: \(evidence.reachedRoutePointIDs.count)/\(expected) · ≥\(WalkthroughEvidence.minimumSamplesPerRoutePoint) GPS в радиусе \(Int(WalkthroughEvidence.routePointRadiusMeters)) м")
                    Text("Замыкание start→finish: \(Int(evidence.startFinishClosureMeters)) м (нужно ≤150 м)")
                    Text("До public start: старт \(Int(evidence.startDistanceToPublicStartMeters)) м · финиш \(Int(evidence.finishDistanceToPublicStartMeters)) м")
                }
                .font(.caption.monospacedDigit())
                .foregroundStyle(evidence.isSufficient(for: mission) ? RunGameTheme.electric : RunGameTheme.warning)
            }
            if let error = recorder.lastError {
                Text(error).font(.footnote).foregroundStyle(RunGameTheme.warning)
                Button("Открыть Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
            }
        }
        .runGamePanel()
    }

    private var approvalChecklist: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Ручное подтверждение").font(.headline)
            Toggle("Тротуары и покрытие подходят", isOn: $appModel.sidewalksChecked)
            Toggle("Переходы понятны и безопасны", isOn: $appModel.crossingsChecked)
            Toggle("Рельеф подходит для этой нагрузки", isOn: $appModel.elevationChecked)
            Toggle("Маршрут проходится без взгляда на экран", isOn: $appModel.screenFreeChecked)
            Button {
                guard let walkthroughEvidence else { return }
                appModel.approveRoute(evidence: walkthroughEvidence)
            } label: {
                Label(
                    appModel.routeApproved ? "Маршрут одобрен на устройстве" : "Одобрить маршрут",
                    systemImage: appModel.routeApproved ? "checkmark.shield.fill" : "shield"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(appModel.routeApproved ? RunGameTheme.electric : RunGameTheme.violet)
            .accessibilityIdentifier("routeApprovalButton")
            .disabled(
                !appModel.checklistComplete
                    || appModel.routeApproved
                    || !(walkthroughEvidence?.isSufficient(for: mission) ?? false)
                    || !planner.isComplete
            )
            if walkthroughEvidence == nil && !appModel.routeApproved {
                Text("Approval станет доступен только после полного сохранённого GPX, прохождения всех контрольных точек и ручного checklist.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("Остановка ради дороги всегда допустима: не двигайся ради GPS. Большой разрыв означает только неполное техническое evidence и необходимость безопасно повторить запись.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .runGamePanel()
    }

    private func finishWalkthrough() {
        if let summary = recorder.stop(completed: true) {
            let evidence = WalkthroughEvidence.make(
                mission: mission,
                summary: summary,
                samples: recorder.samples,
                locationIncidents: recorder.incidents
            )
            walkthroughEvidence = evidence
            if evidence.isSufficient(for: mission) {
                appModel.recordPendingWalkthrough(evidence: evidence)
            }
        }
        appModel.refreshRecoveredTracks()
    }

    private static func region(for points: [RoutePoint]) -> MKCoordinateRegion {
        let latitudes = points.map(\.latitude)
        let longitudes = points.map(\.longitude)
        guard let minLatitude = latitudes.min(), let maxLatitude = latitudes.max(),
              let minLongitude = longitudes.min(), let maxLongitude = longitudes.max() else {
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 0, longitude: 0),
                span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
            )
        }
        let center = CLLocationCoordinate2D(
            latitude: (minLatitude + maxLatitude) / 2,
            longitude: (minLongitude + maxLongitude) / 2
        )
        return MKCoordinateRegion(
            center: center,
            span: MKCoordinateSpan(
                latitudeDelta: max(0.012, (maxLatitude - minLatitude) * 1.8),
                longitudeDelta: max(0.012, (maxLongitude - minLongitude) * 1.8)
            )
        )
    }
}
