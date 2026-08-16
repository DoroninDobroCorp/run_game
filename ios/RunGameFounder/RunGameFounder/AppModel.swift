import Foundation

@MainActor
final class AppModel: ObservableObject {
    private struct QueueTransactionMarker: Codable {
        let schemaVersion: String
        let operation: String
        let runID: String
        let startedAt: Date
    }

    @Published private(set) var participantId: String = ""
    @Published private(set) var mission: MissionConfig?
    @Published private(set) var loadError: String?
    @Published var sidewalksChecked = false
    @Published var crossingsChecked = false
    @Published var elevationChecked = false
    @Published var screenFreeChecked = false
    @Published private(set) var routeApproved = false
    @Published private(set) var homeAudioCompleted = false
    @Published private(set) var routeApprovalEvidence: WalkthroughEvidence?
    @Published private(set) var pendingWalkthroughEvidence: WalkthroughEvidence?
    @Published private(set) var audioApprovalEvidence: AudioApprovalRecord?
    @Published private(set) var recoveredTrackURLs: [URL] = []
    @Published private(set) var localEvidenceURLs: [URL] = []
    @Published private(set) var pendingDebriefs: [RunSessionContext] = []
    @Published private(set) var pendingRecalls: [PendingRecall] = []
    @Published private(set) var queueQuarantineURLs: [URL] = []
    @Published private(set) var journalCorrupted = false
    @Published private(set) var queueCorrupted = false
    @Published private(set) var queuePersistenceFailed = false
    @Published private(set) var journalPersistenceFailed = false
    @Published private(set) var journalErrorBanner: String?
    @Published private(set) var queueErrorBanner: String?

    private let defaults: UserDefaults
    private let documentsDirectory: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(defaults: UserDefaults = .standard, documentsDirectory: URL? = nil, participantId: String? = nil) {
        self.defaults = defaults
        self.documentsDirectory = documentsDirectory
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]

        if let participantId, !participantId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.participantId = participantId
            defaults.set(participantId, forKey: Self.participantIdKey)
        } else if let stored = defaults.string(forKey: Self.participantIdKey), !stored.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.participantId = stored
        } else {
            let generated = "participant_founder_" + UUID().uuidString
            defaults.set(generated, forKey: Self.participantIdKey)
            self.participantId = generated
        }

        loadMission()
        restorePendingDebriefs()
        restorePendingRecalls()
        restoreQueueTransactionMarker()
        refreshQueueQuarantineURLs()
        recoverActiveJournal()
        refreshRecoveredTracks()
    }

    var checklistComplete: Bool {
        sidewalksChecked && crossingsChecked && elevationChecked && screenFreeChecked
    }

    var canStartMission: Bool {
        mission?.m1HumanApprovalComplete == true && routeApproved && homeAudioCompleted
    }

    var canBeginMission: Bool {
        Self.canBeginMission(
            readinessComplete: canStartMission,
            hasPendingDebrief: !pendingDebriefs.isEmpty,
            hasPendingRecall: !pendingRecalls.isEmpty
        ) && !journalCorrupted && !queueCorrupted && !queuePersistenceFailed && !journalPersistenceFailed && loadError == nil
    }

    var evidenceCaptureLocked: Bool {
        !pendingDebriefs.isEmpty || !pendingRecalls.isEmpty || loadError != nil || journalCorrupted || queueCorrupted || queuePersistenceFailed || journalPersistenceFailed
    }

    nonisolated static func canBeginMission(
        readinessComplete: Bool,
        hasPendingDebrief: Bool,
        hasPendingRecall: Bool
    ) -> Bool {
        readinessComplete && !hasPendingDebrief && !hasPendingRecall
    }

    var readinessCompletedSteps: Int {
        [mission != nil, routeApproved, homeAudioCompleted].filter { $0 }.count
    }

    func loadMission() {
        do {
            let loaded = try MissionConfig.loadFromBundle()
            mission = loaded
            loadError = nil
            restoreApprovals(for: loaded)
        } catch {
            mission = nil
            loadError = error.localizedDescription
            routeApproved = false
            homeAudioCompleted = false
            routeApprovalEvidence = nil
            pendingWalkthroughEvidence = nil
            audioApprovalEvidence = nil
        }
    }

    func approveRoute(evidence: WalkthroughEvidence) {
        guard let mission,
              checklistComplete,
              evidence.isSufficient(for: mission),
              trackFileIsIntact(evidence.track) else { return }
        routeApprovalEvidence = evidence
        routeApproved = true
        pendingWalkthroughEvidence = nil
        defaults.removeObject(forKey: Self.pendingWalkthroughKey(for: mission))
        if let data = try? encoder.encode(evidence) {
            defaults.set(data, forKey: Self.routeApprovalKey(for: mission))
        }
    }

    func recordPendingWalkthrough(evidence: WalkthroughEvidence) {
        guard let mission,
              evidence.isSufficient(for: mission),
              trackFileIsIntact(evidence.track) else { return }
        pendingWalkthroughEvidence = evidence
        if let data = try? encoder.encode(evidence) {
            defaults.set(data, forKey: Self.pendingWalkthroughKey(for: mission))
        }
    }

    func markHomeAudioCompleted(record: AudioApprovalRecord) {
        guard let mission, record.isValid(for: mission) else { return }
        audioApprovalEvidence = record
        homeAudioCompleted = true
        if let data = try? encoder.encode(record) {
            defaults.set(data, forKey: Self.audioApprovalKey(for: mission))
        }
    }

    func resetLocalApprovals() {
        let prefixes = [
            Self.routeApprovalPrefix,
            Self.audioApprovalPrefix,
            Self.pendingWalkthroughPrefix,
        ]
        for key in defaults.dictionaryRepresentation().keys
            where prefixes.contains(where: key.hasPrefix) {
            defaults.removeObject(forKey: key)
        }
        routeApproved = false
        homeAudioCompleted = false
        routeApprovalEvidence = nil
        pendingWalkthroughEvidence = nil
        audioApprovalEvidence = nil
        sidewalksChecked = false
        crossingsChecked = false
        elevationChecked = false
        screenFreeChecked = false
    }

    func timelineBlock(at elapsed: TimeInterval) -> TimelineBlock? {
        mission?.timeline.last(where: { elapsed >= $0.start && elapsed < $0.end })
    }

    func refreshRecoveredTracks() {
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: documentsDirectory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )) ?? []
        for url in urls {
            FileDurability.markExcludedFromBackup(url: url)
        }
        recoveredTrackURLs = urls
            .filter { $0.lastPathComponent.hasSuffix(".partial.gpx") }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        let isRecallPending = !pendingRecalls.isEmpty
        localEvidenceURLs = urls
            .filter { url in
                let name = url.lastPathComponent
                let ext = url.pathExtension.lowercased()
                if name.hasSuffix(".partial.gpx") { return false }
                if name.hasSuffix("-draft.json") { return false }
                if name == "pending_debriefs.json" || name == "pending_recalls.json" || name == "pending_queue_transaction.json" || name == ActiveRunJournal.journalFilename { return false }
                if isRecallPending && ext == "json" { return false }
                return ["gpx", "json"].contains(ext)
            }
            .sorted {
                let left = (try? $0.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
                let right = (try? $1.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
                return (left ?? .distantPast) > (right ?? .distantPast)
            }
    }

    func scheduleRecall(for context: RunSessionContext) throws {
        guard context.completed && !context.aborted else { return }
        let pending = PendingRecall.make(context: context)
        var candidate = pendingRecalls.filter { $0.runID != pending.runID }
        candidate.append(pending)
        candidate.sort { $0.dueAt < $1.dueAt }
        do {
            try beginQueueTransaction(operation: "schedule_recall", runID: context.runID)
            try persistPendingRecalls(candidate)
            try clearQueueTransactionMarker()
            pendingRecalls = candidate
            markQueuePersistenceSucceeded()
            refreshRecoveredTracks()
        } catch {
            markQueuePersistenceFailed(operation: "schedule recall", error: error)
            throw error
        }
    }

    func scheduleDebrief(for context: RunSessionContext) throws {
        var candidate = pendingDebriefs.filter { $0.runID != context.runID }
        candidate.append(context)
        candidate.sort { $0.endedAt < $1.endedAt }
        do {
            try beginQueueTransaction(operation: "schedule_debrief", runID: context.runID)
            try persistPendingDebriefs(candidate)
            try clearQueueTransactionMarker()
            pendingDebriefs = candidate
            markQueuePersistenceSucceeded()
            refreshRecoveredTracks()
        } catch {
            markQueuePersistenceFailed(operation: "schedule debrief", error: error)
            throw error
        }
    }

    func completeDebrief(runID: String) throws {
        let candidate = pendingDebriefs.filter { $0.runID != runID }
        do {
            try beginQueueTransaction(operation: "complete_debrief", runID: runID)
            try persistPendingDebriefs(candidate)
            try clearQueueTransactionMarker()
            pendingDebriefs = candidate
            markQueuePersistenceSucceeded()
            refreshRecoveredTracks()
        } catch {
            markQueuePersistenceFailed(operation: "complete debrief", error: error)
            throw error
        }
    }

    func completeRecall(runID: String) throws {
        let candidate = pendingRecalls.filter { $0.runID != runID }
        do {
            try beginQueueTransaction(operation: "complete_recall", runID: runID)
            try persistPendingRecalls(candidate)
            try clearQueueTransactionMarker()
            pendingRecalls = candidate
            markQueuePersistenceSucceeded()
            refreshRecoveredTracks()
        } catch {
            markQueuePersistenceFailed(operation: "complete recall", error: error)
            throw error
        }
    }

    func resetQueueQuarantine() {
        do {
            try quarantineQueueDataIfPresent(at: pendingDebriefsFileURL, label: "pending-debriefs")
            try quarantineQueueDataIfPresent(at: pendingRecallsFileURL, label: "pending-recalls")
            try quarantineQueueDataIfPresent(at: queueTransactionFileURL, label: "queue-transaction")
            try quarantineLegacyQueueDataIfPresent(key: Self.pendingDebriefsKey, label: "legacy-pending-debriefs")
            try quarantineLegacyQueueDataIfPresent(key: Self.pendingRecallsKey, label: "legacy-pending-recalls")

            try persistPendingDebriefs([])
            try persistPendingRecalls([])
            try clearQueueTransactionMarker()
            pendingDebriefs = []
            pendingRecalls = []
            queueCorrupted = false
            queuePersistenceFailed = false
            queueErrorBanner = nil
            refreshQueueQuarantineURLs()
            refreshRecoveredTracks()
        } catch {
            queueCorrupted = true
            queuePersistenceFailed = true
            queueErrorBanner = "Queue quarantine/reset failed: \(error.localizedDescription). Evidence remains locked."
            refreshQueueQuarantineURLs()
        }
    }

    func saveActiveAttempt(_ attempt: ActiveRunAttempt) throws {
        try ActiveRunJournal(defaults: defaults, documentsDirectory: documentsDirectory).save(attempt)
    }

    func clearActiveJournal() throws {
        try ActiveRunJournal(defaults: defaults, documentsDirectory: documentsDirectory).clear()
    }

    func setJournalErrorBanner(_ message: String?) {
        journalErrorBanner = message
    }

    func setJournalPersistenceFailed(_ failed: Bool, message: String? = nil) {
        journalPersistenceFailed = failed
        if let message {
            journalErrorBanner = message
        }
    }

    func resetJournalQuarantine() {
        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: documentsDirectory)
        do {
            let success = try journal.resetQuarantine()
            let fm = FileManager.default
            guard success && !fm.fileExists(atPath: journal.quarantineDirectoryURL.path) else {
                journalErrorBanner = "Failed to reset quarantine: Directory deletion unverified"
                recoverActiveJournal()
                return
            }
            journalCorrupted = false
            journalPersistenceFailed = false
            journalErrorBanner = nil
        } catch {
            journalErrorBanner = "Failed to reset quarantine: \(error.localizedDescription)"
        }
        recoverActiveJournal()
    }

    func recoverActiveJournal() {
        let journal = ActiveRunJournal(defaults: defaults, documentsDirectory: documentsDirectory)
        switch journal.loadJournal() {
        case .attempt(let attempt):
            let endedAt = Date()
            var recoveredTrack: TrackSummary? = nil
            if let basename = attempt.partialGPXBasename,
               !basename.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               URL(fileURLWithPath: basename).lastPathComponent == basename,
               !basename.contains("/"),
               !basename.contains("\\"),
               !basename.contains("..") {
                let trackURL = documentsDirectory.appendingPathComponent(basename)
                if FileManager.default.fileExists(atPath: trackURL.path),
                   let fileData = try? Data(contentsOf: trackURL),
                   let samples = try? GPXDocument.parseSamples(from: fileData),
                   !samples.isEmpty {
                    let sha = try? BundleIntegrity.sha256(of: trackURL)
                    recoveredTrack = try? TrackSummary.make(
                        fileName: basename,
                        samples: samples,
                        fileSHA256: sha
                    )
                }
            }

            let recoveredContext = RunSessionContext(
                participantID: attempt.participantID,
                runID: attempt.runID,
                missionID: attempt.missionID,
                bindingID: attempt.bindingID,
                audioSHA256: attempt.audioSHA256,
                routeWorkoutFingerprint: attempt.routeWorkoutFingerprint,
                condition: attempt.condition,
                startedAt: attempt.startedAt,
                endedAt: endedAt,
                precommittedNextWorkoutAt: attempt.precommittedNextWorkoutAt,
                completed: false,
                aborted: true,
                abortReason: "App relaunch recovery: session interrupted in \(attempt.phase.rawValue) phase",
                audioElapsedSeconds: attempt.audioElapsedSeconds,
                pauseCount: attempt.pauseCount,
                track: recoveredTrack,
                routeTraversalEvidence: nil,
                audioIncidents: attempt.audioIncidents + ["Interrupted by unexpected process termination"],
                locationIncidents: attempt.locationIncidents
            )
            do {
                try scheduleDebrief(for: recoveredContext)
                try journal.clear()
                journalCorrupted = false
                journalPersistenceFailed = false
                journalErrorBanner = nil
            } catch {
                journalErrorBanner = "Relaunch recovery failed to persist debrief durably: \(error.localizedDescription)"
            }
        case .corrupted(let reason):
            journalCorrupted = true
            journalErrorBanner = "Corrupted active run journal: \(reason). Evidence capture is locked."
        case .none:
            journalCorrupted = false
            journalPersistenceFailed = false
            journalErrorBanner = nil
        }
    }

    var pendingDebriefsFileURL: URL {
        documentsDirectory.appendingPathComponent("pending_debriefs.json")
    }

    var pendingRecallsFileURL: URL {
        documentsDirectory.appendingPathComponent("pending_recalls.json")
    }

    var queueQuarantineDirectoryURL: URL {
        documentsDirectory.appendingPathComponent("QueueQuarantine", isDirectory: true)
    }

    var queueTransactionFileURL: URL {
        documentsDirectory.appendingPathComponent("pending_queue_transaction.json")
    }

    private func restorePendingRecalls() {
        let fm = FileManager.default
        let data: Data
        if fm.fileExists(atPath: pendingRecallsFileURL.path) {
            do {
                data = try Data(contentsOf: pendingRecallsFileURL)
            } catch {
                queueCorrupted = true
                queueErrorBanner = "Pending recall queue is unreadable: \(error.localizedDescription). Evidence is locked."
                pendingRecalls = []
                return
            }
        } else if let legacyData = defaults.data(forKey: Self.pendingRecallsKey) {
            data = legacyData
        } else {
            pendingRecalls = []
            return
        }

        do {
            let records = try decoder.decode([PendingRecall].self, from: data)
            pendingRecalls = Dictionary(grouping: records, by: \.runID)
                .compactMap { $0.value.last }
                .sorted { $0.dueAt < $1.dueAt }
            if !fm.fileExists(atPath: pendingRecallsFileURL.path) {
                do {
                    try persistPendingRecalls(pendingRecalls)
                } catch {
                    queuePersistenceFailed = true
                    queueErrorBanner = "Pending recall migration failed: \(error.localizedDescription). Evidence is locked."
                }
            }
        } catch {
            queueCorrupted = true
            queueErrorBanner = "Pending recall queue is corrupted: \(error.localizedDescription). Evidence is locked."
            pendingRecalls = []
        }
    }

    private func restorePendingDebriefs() {
        let fm = FileManager.default
        let data: Data
        if fm.fileExists(atPath: pendingDebriefsFileURL.path) {
            do {
                data = try Data(contentsOf: pendingDebriefsFileURL)
            } catch {
                queueCorrupted = true
                queueErrorBanner = "Pending debrief queue is unreadable: \(error.localizedDescription). Evidence is locked."
                pendingDebriefs = []
                return
            }
        } else if let legacyData = defaults.data(forKey: Self.pendingDebriefsKey) {
            data = legacyData
        } else {
            pendingDebriefs = []
            return
        }

        do {
            let records = try decoder.decode([RunSessionContext].self, from: data)
            pendingDebriefs = Dictionary(grouping: records, by: \.runID)
                .compactMap { $0.value.last }
                .sorted { $0.endedAt < $1.endedAt }
            if !fm.fileExists(atPath: pendingDebriefsFileURL.path) {
                do {
                    try persistPendingDebriefs(pendingDebriefs)
                } catch {
                    queuePersistenceFailed = true
                    queueErrorBanner = "Pending debrief migration failed: \(error.localizedDescription). Evidence is locked."
                }
            }
        } catch {
            queueCorrupted = true
            queueErrorBanner = "Pending debrief queue is corrupted: \(error.localizedDescription). Evidence is locked."
            pendingDebriefs = []
        }
    }

    private func persistPendingDebriefs(_ records: [RunSessionContext]) throws {
        let data = try encoder.encode(records)
        try FileDurability.writeAtomicStaging(data: data, to: pendingDebriefsFileURL, overwrite: true)
        let readBackData = try Data(contentsOf: pendingDebriefsFileURL)
        let verifiedRecords = try decoder.decode([RunSessionContext].self, from: readBackData)
        guard verifiedRecords.map(\.runID) == records.map(\.runID) else {
            throw FounderAppError.invalidTrack("Pending debrief read-back verification failed")
        }
        if defaults.object(forKey: Self.pendingDebriefsKey) != nil {
            defaults.removeObject(forKey: Self.pendingDebriefsKey)
        }
    }

    private func persistPendingRecalls(_ records: [PendingRecall]) throws {
        let data = try encoder.encode(records)
        try FileDurability.writeAtomicStaging(data: data, to: pendingRecallsFileURL, overwrite: true)
        let readBackData = try Data(contentsOf: pendingRecallsFileURL)
        let verifiedRecords = try decoder.decode([PendingRecall].self, from: readBackData)
        guard verifiedRecords.map(\.runID) == records.map(\.runID) else {
            throw FounderAppError.invalidTrack("Pending recall read-back verification failed")
        }
        if defaults.object(forKey: Self.pendingRecallsKey) != nil {
            defaults.removeObject(forKey: Self.pendingRecallsKey)
        }
    }

    private func markQueuePersistenceFailed(operation: String, error: Error) {
        queuePersistenceFailed = true
        queueErrorBanner = "Failed to \(operation) durably: \(error.localizedDescription). Evidence remains locked."
    }

    private func markQueuePersistenceSucceeded() {
        queuePersistenceFailed = false
        if !queueCorrupted {
            queueErrorBanner = nil
        }
    }

    private func beginQueueTransaction(operation: String, runID: String) throws {
        let marker = QueueTransactionMarker(
            schemaVersion: "0.1",
            operation: operation,
            runID: runID,
            startedAt: Date()
        )
        let data = try encoder.encode(marker)
        try FileDurability.writeAtomicStaging(data: data, to: queueTransactionFileURL, overwrite: true)
        guard try Data(contentsOf: queueTransactionFileURL) == data else {
            throw FounderAppError.invalidTrack("Queue transaction marker verification failed")
        }
    }

    private func clearQueueTransactionMarker() throws {
        try FileDurability.removeDurably(at: queueTransactionFileURL)
    }

    private func restoreQueueTransactionMarker() {
        guard FileManager.default.fileExists(atPath: queueTransactionFileURL.path) else { return }
        queuePersistenceFailed = true
        let detail: String
        if let data = try? Data(contentsOf: queueTransactionFileURL),
           let marker = try? decoder.decode(QueueTransactionMarker.self, from: data) {
            detail = "Interrupted queue operation \(marker.operation) for run \(marker.runID)."
        } else {
            detail = "Unreadable interrupted queue transaction marker."
        }
        queueErrorBanner = "\(detail) Evidence remains locked until the queue is retried or quarantined."
    }

    private func quarantineQueueDataIfPresent(at url: URL, label: String) throws {
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        try quarantineQueueData(try Data(contentsOf: url), label: label)
    }

    private func quarantineLegacyQueueDataIfPresent(key: String, label: String) throws {
        guard let data = defaults.data(forKey: key) else { return }
        try quarantineQueueData(data, label: label)
    }

    private func quarantineQueueData(_ data: Data, label: String) throws {
        let filename = "\(label)-\(UUID().uuidString).json"
        let destination = queueQuarantineDirectoryURL.appendingPathComponent(filename)
        try FileDurability.writeFinalEvidence(data: data, to: destination)
    }

    private func refreshQueueQuarantineURLs() {
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: queueQuarantineDirectoryURL,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )) ?? []
        queueQuarantineURLs = urls.sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private func restoreApprovals(for mission: MissionConfig) {
        routeApprovalEvidence = nil
        pendingWalkthroughEvidence = nil
        audioApprovalEvidence = nil

        if let data = defaults.data(forKey: Self.routeApprovalKey(for: mission)),
            let evidence = try? decoder.decode(WalkthroughEvidence.self, from: data),
            evidence.isSufficient(for: mission),
            trackFileIsIntact(evidence.track)
        {
            routeApprovalEvidence = evidence
            routeApproved = true
        } else {
            routeApproved = false
        }

        if !routeApproved,
           let data = defaults.data(forKey: Self.pendingWalkthroughKey(for: mission)),
           let evidence = try? decoder.decode(WalkthroughEvidence.self, from: data),
           evidence.isSufficient(for: mission),
           trackFileIsIntact(evidence.track) {
            pendingWalkthroughEvidence = evidence
        }

        if
            let data = defaults.data(forKey: Self.audioApprovalKey(for: mission)),
            let record = try? decoder.decode(AudioApprovalRecord.self, from: data),
            record.isValid(for: mission)
        {
            audioApprovalEvidence = record
            homeAudioCompleted = true
        } else {
            homeAudioCompleted = false
        }
    }

    private static func routeApprovalKey(for mission: MissionConfig) -> String {
        routeApprovalPrefix + mission.routeWorkoutFingerprint
    }

    private static func audioApprovalKey(for mission: MissionConfig) -> String {
        audioApprovalPrefix + mission.audioSHA256.lowercased()
    }

    private static func pendingWalkthroughKey(for mission: MissionConfig) -> String {
        pendingWalkthroughPrefix + mission.routeWorkoutFingerprint
    }

    private func trackFileIsIntact(_ track: TrackSummary) -> Bool {
        let fileName = track.fileName
        guard URL(fileURLWithPath: fileName).lastPathComponent == fileName,
              !fileName.contains("/"),
              !fileName.contains("\\") else { return false }
        let url = documentsDirectory.appendingPathComponent(fileName)
        guard FileDurability.verifySHA256(of: url, expectedSHA: track.fileSHA256) else { return false }
        FileDurability.markExcludedFromBackup(url: url)
        return true
    }

    static let participantIdKey = "rungame.preference.participant_id"
    private static let routeApprovalPrefix = "founder.v2.routeApproved."
    private static let audioApprovalPrefix = "founder.v2.homeAudioCompleted."
    private static let pendingWalkthroughPrefix = "founder.v2.pendingWalkthrough."
    private static let pendingRecallsKey = "founder.v2.pendingRecalls"
    private static let pendingDebriefsKey = "founder.v2.pendingDebriefs"
}
