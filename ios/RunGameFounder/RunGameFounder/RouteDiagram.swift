import SwiftUI

/// A geographic route drawing that remains legible without downloaded map tiles.
struct RouteDiagram: View {
    let route: OfflineRoute
    var progress: Double = 0

    var body: some View {
        Canvas { context, size in
            guard let minLat = route.coordinates.map(\.latitude).min(),
                  let maxLat = route.coordinates.map(\.latitude).max(),
                  let minLon = route.coordinates.map(\.longitude).min(),
                  let maxLon = route.coordinates.map(\.longitude).max() else { return }
            let correction = cos((minLat + maxLat) / 2 * .pi / 180)
            let width = max(0.00001, (maxLon - minLon) * correction)
            let height = max(0.00001, maxLat - minLat)
            let scale = min((size.width - 64) / width, (size.height - 64) / height)
            let origin = CGPoint(x: (size.width - width * scale) / 2, y: (size.height - height * scale) / 2)
            func project(_ point: RouteCoordinate) -> CGPoint {
                CGPoint(x: origin.x + (point.longitude - minLon) * correction * scale,
                        y: origin.y + (maxLat - point.latitude) * scale)
            }
            var grid = Path()
            for x in stride(from: 0.0, through: size.width, by: 28) {
                grid.move(to: CGPoint(x: x, y: 0)); grid.addLine(to: CGPoint(x: x, y: size.height))
            }
            for y in stride(from: 0.0, through: size.height, by: 28) {
                grid.move(to: CGPoint(x: 0, y: y)); grid.addLine(to: CGPoint(x: size.width, y: y))
            }
            context.stroke(grid, with: .color(.white.opacity(0.035)), lineWidth: 1)
            var path = Path()
            for (index, coordinate) in route.coordinates.enumerated() {
                if index == 0 { path.move(to: project(coordinate)) }
                else { path.addLine(to: project(coordinate)) }
            }
            context.stroke(path, with: .color(RunGameTheme.electric.opacity(0.1)), style: StrokeStyle(lineWidth: 18, lineCap: .round, lineJoin: .round))
            context.stroke(path, with: .color(RunGameTheme.electric), style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
            for (number, index) in route.waypointIndices.dropLast().enumerated() where route.coordinates.indices.contains(index) {
                let point = project(route.coordinates[index])
                let circle = Path(ellipseIn: CGRect(x: point.x - 12, y: point.y - 12, width: 24, height: 24))
                context.fill(circle, with: .color(number == 0 ? RunGameTheme.electric : RunGameTheme.violet))
                context.draw(Text(number == 0 ? "С" : "\(number)").font(.system(size: 11, weight: .black)).foregroundColor(RunGameTheme.ink), at: point)
            }
            if progress > 0, let current = route.coordinate(at: progress) {
                let point = project(current)
                let circle = Path(ellipseIn: CGRect(x: point.x - 7, y: point.y - 7, width: 14, height: 14))
                context.fill(circle, with: .color(.white))
                context.stroke(circle, with: .color(RunGameTheme.ink), lineWidth: 3)
            }
        }
        .overlay(alignment: .topLeading) {
            Label("СЕВЕР", systemImage: "arrow.up").font(.system(size: 9, weight: .bold)).tracking(2)
                .foregroundStyle(.secondary).padding(16)
        }
        .background(RunGameTheme.ink.opacity(0.7))
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .accessibilityLabel("Офлайн-схема замкнутого маршрута, \(route.waypointIndices.count - 1) контрольные точки")
    }
}
