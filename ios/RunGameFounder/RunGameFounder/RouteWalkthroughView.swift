import MapKit
import SwiftUI

struct RouteWalkthroughView: View {
    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    @StateObject private var planner = RoutePlanner()
    @StateObject private var recorder = LocationRecorder()
    @State private var cameraPosition: MapCameraPosition

    init(mission: MissionConfig) {
        self.mission = mission
        _cameraPosition = State(initialValue: .region(Self.region(for: mission.routePoints)))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
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
        .task { await planner.load(points: mission.routePoints) }
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
            } else if planner.distanceMeters > 0 {
                Text("≈ \(planner.distanceMeters / 1000, specifier: "%.1f") км · обычная ходьба ≈ \(Int(planner.expectedTravelTime / 60)) мин")
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
                    Text("Запись · \(recorder.samples.count) точек")
                        .font(.subheadline.monospacedDigit())
                }
                Button("Завершить обход и сохранить GPX", role: .destructive) {
                    recorder.stop(prefix: "valparaiso-walkthrough")
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.danger)
            } else {
                Button {
                    recorder.requestPermission()
                    recorder.start()
                } label: {
                    Label("Начать дневной обход", systemImage: "location.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(RunGameTheme.electric)
            }
            if let url = recorder.exportedURL {
                ShareLink(item: url) {
                    Label("Экспортировать GPX", systemImage: "square.and.arrow.up")
                }
            }
            if let error = recorder.lastError {
                Text(error).font(.footnote).foregroundStyle(RunGameTheme.warning)
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
                appModel.approveRoute()
            } label: {
                Label(
                    appModel.routeApproved ? "Маршрут одобрен на устройстве" : "Одобрить маршрут",
                    systemImage: appModel.routeApproved ? "checkmark.shield.fill" : "shield"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(appModel.routeApproved ? RunGameTheme.electric : RunGameTheme.violet)
            .disabled(!appModel.checklistComplete || appModel.routeApproved)
        }
        .runGamePanel()
    }

    private static func region(for points: [RoutePoint]) -> MKCoordinateRegion {
        let latitudes = points.map(\.latitude)
        let longitudes = points.map(\.longitude)
        let center = CLLocationCoordinate2D(
            latitude: (latitudes.min()! + latitudes.max()!) / 2,
            longitude: (longitudes.min()! + longitudes.max()!) / 2
        )
        return MKCoordinateRegion(
            center: center,
            span: MKCoordinateSpan(
                latitudeDelta: max(0.012, (latitudes.max()! - latitudes.min()!) * 1.8),
                longitudeDelta: max(0.012, (longitudes.max()! - longitudes.min()!) * 1.8)
            )
        )
    }
}
