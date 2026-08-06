import CoreLocation
import Foundation

struct MissionConfig: Codable {
    let schemaVersion: String
    let missionID: String
    let title: String
    let subtitle: String
    let locationDisplayName: String
    let bindingID: String
    let audioFile: String
    let audioSHA256: String
    let durationSeconds: TimeInterval
    let routeInitiallyApproved: Bool
    let workoutInitiallyApproved: Bool
    let routePoints: [RoutePoint]
    let timeline: [TimelineBlock]
    let evidenceNotice: String

    static func loadFromBundle() throws -> MissionConfig {
        guard let url = Bundle.main.url(forResource: "mission", withExtension: "json") else {
            throw FounderAppError.missingResource("mission.json")
        }
        return try JSONDecoder().decode(MissionConfig.self, from: Data(contentsOf: url))
    }
}

struct RoutePoint: Codable, Identifiable, Hashable {
    let id: String
    let role: String
    let roleLabel: String
    let name: String
    let latitude: Double
    let longitude: Double
    let osmURL: URL

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
}

struct TimelineBlock: Codable, Identifiable, Equatable {
    var id: String { "\(start)-\(end)-\(kind)" }
    let start: TimeInterval
    let end: TimeInterval
    let label: String
    let kind: String
}

enum SessionMode: String, Codable {
    case walkthrough
    case mission
}

struct TrackSample: Codable, Identifiable, Equatable {
    let id: UUID
    let latitude: Double
    let longitude: Double
    let elevation: Double
    let horizontalAccuracy: Double
    let timestamp: Date

    init(location: CLLocation) {
        id = UUID()
        latitude = location.coordinate.latitude
        longitude = location.coordinate.longitude
        elevation = location.altitude
        horizontalAccuracy = location.horizontalAccuracy
        timestamp = location.timestamp
    }

    init(
        id: UUID = UUID(),
        latitude: Double,
        longitude: Double,
        elevation: Double,
        horizontalAccuracy: Double,
        timestamp: Date
    ) {
        self.id = id
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.horizontalAccuracy = horizontalAccuracy
        self.timestamp = timestamp
    }
}

struct DebriefRecord: Codable {
    let schemaVersion: String
    let missionID: String
    let bindingID: String
    let completedAt: Date
    let completed: Bool
    let aborted: Bool
    let abortReason: String
    let missionGoal: String
    let memorableScene: String
    let attentionDrop: String
    let movementEffect: String
    let desireForM02: Int
    let placeNecessity: Int
    let notes: String
}

enum FounderAppError: LocalizedError {
    case missingResource(String)
    case noRecordedTrack

    var errorDescription: String? {
        switch self {
        case .missingResource(let name):
            return "Не найден локальный ресурс: \(name). Сначала подготовьте iOS bundle."
        case .noRecordedTrack:
            return "Маршрут ещё не записан."
        }
    }
}

enum Formatters {
    static func clock(_ seconds: TimeInterval) -> String {
        let value = max(0, Int(seconds.rounded(.down)))
        return String(format: "%02d:%02d", value / 60, value % 60)
    }
}
