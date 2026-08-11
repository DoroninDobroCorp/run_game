import Foundation

enum ActiveRunPhase: String, Codable {
    case acquiringGPS
    case running
}

struct ActiveRunAttempt: Codable, Equatable {
    let schemaVersion: String
    let participantID: String
    let runID: String
    let missionID: String
    let bindingID: String
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let partialGPXBasename: String?
    let condition: String
    let phase: ActiveRunPhase
    let startedAt: Date
    let precommittedNextWorkoutAt: Date
    let pauseCount: Int
    let audioIncidents: [String]
    let locationIncidents: [String]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case participantID = "participant_id"
        case runID = "run_id"
        case missionID = "mission_id"
        case bindingID = "binding_id"
        case audioSHA256 = "audio_sha256"
        case routeWorkoutFingerprint = "route_workout_fingerprint"
        case partialGPXBasename = "partial_gpx_basename"
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
        participantID: String = "participant_founder_default",
        runID: String,
        missionID: String,
        bindingID: String,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        partialGPXBasename: String? = nil,
        condition: String = "A",
        phase: ActiveRunPhase,
        startedAt: Date,
        precommittedNextWorkoutAt: Date = Date().addingTimeInterval(48 * 3600),
        pauseCount: Int = 0,
        audioIncidents: [String] = [],
        locationIncidents: [String] = []
    ) {
        self.schemaVersion = schemaVersion
        self.participantID = participantID
        self.runID = runID
        self.missionID = missionID
        self.bindingID = bindingID
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.partialGPXBasename = partialGPXBasename
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
    static let journalFilename = "active_run_journal.json"

    private let defaults: UserDefaults
    private let documentsDirectory: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(
        defaults: UserDefaults = .standard,
        documentsDirectory: URL? = nil
    ) {
        self.defaults = defaults
        self.documentsDirectory = documentsDirectory
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]

        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        self.encoder = enc

        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .iso8601
        self.decoder = dec
    }

    var journalFileURL: URL {
        documentsDirectory.appendingPathComponent(Self.journalFilename)
    }

    var quarantineDirectoryURL: URL {
        documentsDirectory.appendingPathComponent(".quarantine", isDirectory: true)
    }

    var currentAttempt: ActiveRunAttempt? {
        guard case .attempt(let attempt) = loadJournal() else { return nil }
        return attempt
    }

    func loadJournal() -> ActiveRunJournalResult {
        let fileManager = FileManager.default
        let data: Data
        if fileManager.fileExists(atPath: journalFileURL.path) {
            do {
                data = try Data(contentsOf: journalFileURL)
            } catch {
                let reason = "Failed to read active journal file: \(error.localizedDescription)"
                quarantineCorruptedJournal(reason: reason, rawData: Data())
                return .corrupted(reason)
            }
        } else if let legacyData = defaults.data(forKey: Self.journalKey) {
            data = legacyData
        } else {
            return .none
        }

        do {
            let attempt = try decoder.decode(ActiveRunAttempt.self, from: data)
            guard attempt.schemaVersion == "0.1" else {
                let reason = "Unsupported active journal schema version \(attempt.schemaVersion)"
                quarantineCorruptedJournal(reason: reason, rawData: data)
                return .corrupted(reason)
            }
            return .attempt(attempt)
        } catch {
            let reason = "Corrupted active journal data: \(error.localizedDescription)"
            quarantineCorruptedJournal(reason: reason, rawData: data)
            return .corrupted(reason)
        }
    }

    func save(_ attempt: ActiveRunAttempt) {
        do {
            let data = try encoder.encode(attempt)
            try FileDurability.writeAtomicStaging(data: data, to: journalFileURL, overwrite: true)
            defaults.set(data, forKey: Self.journalKey)
        } catch {
            // Fail closed log or handling
        }
    }

    func clear() {
        defaults.removeObject(forKey: Self.journalKey)
        try? FileManager.default.removeItem(at: journalFileURL)
    }

    @discardableResult
    func quarantineCorruptedJournal(reason: String, rawData: Data) -> URL? {
        defaults.removeObject(forKey: Self.journalKey)
        try? FileManager.default.removeItem(at: journalFileURL)

        do {
            try FileManager.default.createDirectory(at: quarantineDirectoryURL, withIntermediateDirectories: true)
            let isoDate = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
            let filename = "corrupted-journal-\(isoDate)-\(UUID().uuidString.prefix(6)).json"
            let destination = quarantineDirectoryURL.appendingPathComponent(filename)
            try FileDurability.writeAtomicStaging(data: rawData, to: destination, overwrite: true)
            return destination
        } catch {
            return nil
        }
    }

    @discardableResult
    func resetQuarantine() -> Bool {
        guard FileManager.default.fileExists(atPath: quarantineDirectoryURL.path) else { return true }
        do {
            try FileManager.default.removeItem(at: quarantineDirectoryURL)
            return true
        } catch {
            return false
        }
    }
}
