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
    let audioElapsedSeconds: TimeInterval
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
        case audioElapsedSeconds = "audio_elapsed_seconds"
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
        audioElapsedSeconds: TimeInterval = 0,
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
        self.audioElapsedSeconds = audioElapsedSeconds
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
        let fromLegacy: Bool
        if fileManager.fileExists(atPath: journalFileURL.path) {
            fromLegacy = false
            do {
                data = try Data(contentsOf: journalFileURL)
            } catch {
                let reason = "Failed to read active journal file: \(error.localizedDescription)"
                _ = try? quarantineCorruptedJournal(reason: reason, rawData: nil)
                return .corrupted(reason)
            }
        } else if let legacyData = defaults.data(forKey: Self.journalKey) {
            fromLegacy = true
            data = legacyData
        } else {
            return .none
        }

        do {
            let attempt = try decoder.decode(ActiveRunAttempt.self, from: data)
            guard attempt.schemaVersion == "0.1" else {
                let reason = "Unsupported active journal schema version \(attempt.schemaVersion)"
                _ = try? quarantineCorruptedJournal(reason: reason, rawData: data)
                return .corrupted(reason)
            }
            if fromLegacy {
                try? save(attempt)
            }
            return .attempt(attempt)
        } catch {
            let reason = "Corrupted active journal data: \(error.localizedDescription)"
            _ = try? quarantineCorruptedJournal(reason: reason, rawData: data)
            return .corrupted(reason)
        }
    }

    func save(_ attempt: ActiveRunAttempt) throws {
        let data = try encoder.encode(attempt)
        try FileDurability.writeAtomicStaging(data: data, to: journalFileURL, overwrite: true)
        if defaults.object(forKey: Self.journalKey) != nil {
            defaults.removeObject(forKey: Self.journalKey)
        }
    }

    func clear() throws {
        if defaults.object(forKey: Self.journalKey) != nil {
            defaults.removeObject(forKey: Self.journalKey)
        }
        if FileManager.default.fileExists(atPath: journalFileURL.path) {
            try FileManager.default.removeItem(at: journalFileURL)
        }
    }

    @discardableResult
    func quarantineCorruptedJournal(reason: String, rawData: Data? = nil) throws -> URL {
        let fileManager = FileManager.default
        let bytesToSave: Data
        if let rawData, !rawData.isEmpty {
            bytesToSave = rawData
        } else if fileManager.fileExists(atPath: journalFileURL.path) {
            bytesToSave = try Data(contentsOf: journalFileURL)
        } else if let legacyData = defaults.data(forKey: Self.journalKey) {
            bytesToSave = legacyData
        } else {
            throw CocoaError(.fileReadNoSuchFile, userInfo: [NSLocalizedDescriptionKey: "No journal data available to quarantine"])
        }

        if defaults.object(forKey: Self.journalKey) != nil {
            defaults.removeObject(forKey: Self.journalKey)
        }
        try fileManager.createDirectory(at: quarantineDirectoryURL, withIntermediateDirectories: true)
        let isoDate = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        let filename = "corrupted-journal-\(isoDate)-\(UUID().uuidString.prefix(6)).json"
        let destination = quarantineDirectoryURL.appendingPathComponent(filename)

        try FileDurability.writeAtomicStaging(data: bytesToSave, to: destination, overwrite: true)

        guard fileManager.fileExists(atPath: destination.path) else {
            throw CocoaError(.fileWriteUnknown, userInfo: [NSLocalizedDescriptionKey: "Quarantine file unverified: destination file missing"])
        }
        let publishedData = try Data(contentsOf: destination)
        guard publishedData == bytesToSave else {
            throw CocoaError(.fileWriteUnknown, userInfo: [NSLocalizedDescriptionKey: "Quarantine file unverified: byte content mismatch"])
        }

        if fileManager.fileExists(atPath: journalFileURL.path) {
            try fileManager.removeItem(at: journalFileURL)
        }
        return destination
    }

    @discardableResult
    func resetQuarantine() throws -> Bool {
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: quarantineDirectoryURL.path) else { return true }
        try fileManager.removeItem(at: quarantineDirectoryURL)
        if fileManager.fileExists(atPath: quarantineDirectoryURL.path) {
            throw CocoaError(.fileWriteUnknown, userInfo: [NSLocalizedDescriptionKey: "Quarantine directory deletion unverified"])
        }
        return true
    }
}
