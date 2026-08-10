import Foundation

enum ActiveRunPhase: String, Codable {
    case acquiringGPS
    case running
}

struct ActiveRunAttempt: Codable, Equatable {
    let schemaVersion: String
    let runID: String
    let missionID: String
    let bindingID: String
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let condition: String
    let phase: ActiveRunPhase
    let startedAt: Date
    let precommittedNextWorkoutAt: Date
    let pauseCount: Int
    let audioIncidents: [String]
    let locationIncidents: [String]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case runID = "run_id"
        case missionID = "mission_id"
        case bindingID = "binding_id"
        case audioSHA256 = "audio_sha256"
        case routeWorkoutFingerprint = "route_workout_fingerprint"
        case condition
        case phase
        case startedAt = "started_at"
        case precommittedNextWorkoutAt = "precommitted_next_workout_at"
        case pauseCount = "pause_count"
        case audioIncidents = "audio_incidents"
        case locationIncidents = "location_incidents"
    }

    init(
        schemaVersion: String = "0.1",
        runID: String,
        missionID: String,
        bindingID: String,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        condition: String = "A",
        phase: ActiveRunPhase,
        startedAt: Date,
        precommittedNextWorkoutAt: Date = Date().addingTimeInterval(48 * 3600),
        pauseCount: Int = 0,
        audioIncidents: [String] = [],
        locationIncidents: [String] = []
    ) {
        self.schemaVersion = schemaVersion
        self.runID = runID
        self.missionID = missionID
        self.bindingID = bindingID
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.condition = condition
        self.phase = phase
        self.startedAt = startedAt
        self.precommittedNextWorkoutAt = precommittedNextWorkoutAt
        self.pauseCount = pauseCount
        self.audioIncidents = audioIncidents
        self.locationIncidents = locationIncidents
    }
}

enum ActiveRunJournalResult {
    case none
    case attempt(ActiveRunAttempt)
    case corrupted(String)
}

final class ActiveRunJournal {
    static let journalKey = "founder.activeRunJournal"
    private let defaults: UserDefaults
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        self.encoder = enc

        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .iso8601
        self.decoder = dec
    }

    var currentAttempt: ActiveRunAttempt? {
        guard case .attempt(let attempt) = loadJournal() else { return nil }
        return attempt
    }

    func loadJournal() -> ActiveRunJournalResult {
        guard let data = defaults.data(forKey: Self.journalKey) else {
            return .none
        }
        do {
            let attempt = try decoder.decode(ActiveRunAttempt.self, from: data)
            guard attempt.schemaVersion == "0.1" else {
                return .corrupted("Unsupported active journal schema version \(attempt.schemaVersion)")
            }
            return .attempt(attempt)
        } catch {
            return .corrupted("Corrupted active journal data: \(error.localizedDescription)")
        }
    }

    func save(_ attempt: ActiveRunAttempt) {
        if let data = try? encoder.encode(attempt) {
            defaults.set(data, forKey: Self.journalKey)
        }
    }

    func clear() {
        defaults.removeObject(forKey: Self.journalKey)
    }
}
