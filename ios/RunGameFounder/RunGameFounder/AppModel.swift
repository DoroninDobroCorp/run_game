import Foundation

@MainActor
final class AppModel: ObservableObject {
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
    @Published private(set) var journalCorrupted = false
    @Published private(set) var queueCorrupted = false
    @Published private(set) var journalErrorBanner: String?

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
        ) && !journalCorrupted && !queueCorrupted && loadError == nil
    }

    var evidenceCaptureLocked: Bool {
        !pendingDebriefs.isEmpty || !pendingRecalls.isEmpty || loadError != nil || journalCorrupted || queueCorrupted
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
                if name == "pending_debriefs.json" || name == "pending_recalls.json" || name == ActiveRunJournal.journalFilename { return false }
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
        pendingRecalls.removeAll { $0.runID == pending.runID }
        pendingRecalls.append(pending)
        pendingRecalls.sort { $0.dueAt < $1.dueAt }
        try persistPendingRecallsAndVerify(expectedRunID: pending.runID)
        refreshRecoveredTracks()
    }

    func scheduleDebrief(for context: RunSessionContext) throws {
        pendingDebriefs.removeAll { $0.runID == context.runID }
        pendingDebriefs.append(context)
        pendingDebriefs.sort { $0.endedAt < $1.endedAt }
        try persistPendingDebriefsAndVerify(expectedRunID: context.runID)
        refreshRecoveredTracks()
    }

    func completeDebrief(runID: String) throws {
        pendingDebriefs.removeAll { $0.runID == runID }
        try persistPendingDebriefs()
        refreshRecoveredTracks()
    }

    func completeRecall(runID: String) throws {
        pendingRecalls.removeAll { $0.runID == runID }
        try persistPendingRecalls()
        refreshRecoveredTracks()
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
                journalErrorBanner = nil
            } catch {
                journalErrorBanner = "Relaunch recovery failed to persist debrief durably: \(error.localizedDescription)"
            }
        case .corrupted(let reason):
            journalCorrupted = true
            journalErrorBanner = "Corrupted active run journal: \(reason). Evidence capture is locked."
        case .none:
            journalCorrupted = false
            journalErrorBanner = nil
        }
    }

    var pendingDebriefsFileURL: URL {
        documentsDirectory.appendingPathComponent("pending_debriefs.json")
    }

    var pendingRecallsFileURL: URL {
        documentsDirectory.appendingPathComponent("pending_recalls.json")
    }

    private func restorePendingRecalls() {
        let fm = FileManager.default
        let data: Data
        if fm.fileExists(atPath: pendingRecallsFileURL.path) {
            do {
                data = try Data(contentsOf: pendingRecallsFileURL)
            } catch {
                queueCorrupted = true
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
                try? persistPendingRecalls()
            }
        } catch {
            queueCorrupted = true
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
                try? persistPendingDebriefs()
            }
        } catch {
            queueCorrupted = true
            pendingDebriefs = []
        }
    }

    private func persistPendingDebriefs() throws {
        let data = try encoder.encode(pendingDebriefs)
        try FileDurability.writeAtomicStaging(data: data, to: pendingDebriefsFileURL, overwrite: true)
        if defaults.object(forKey: Self.pendingDebriefsKey) != nil {
            defaults.removeObject(forKey: Self.pendingDebriefsKey)
        }
    }

    private func persistPendingDebriefsAndVerify(expectedRunID: String) throws {
        try persistPendingDebriefs()
        let readBackData = try Data(contentsOf: pendingDebriefsFileURL)
        let verifiedRecords = try decoder.decode([RunSessionContext].self, from: readBackData)
        guard verifiedRecords.contains(where: { $0.runID == expectedRunID }) else {
            throw FounderAppError.invalidTrack("Pending debrief read-back verification failed for \(expectedRunID)")
        }
    }

    private func persistPendingRecalls() throws {
        let data = try encoder.encode(pendingRecalls)
        try FileDurability.writeAtomicStaging(data: data, to: pendingRecallsFileURL, overwrite: true)
        if defaults.object(forKey: Self.pendingRecallsKey) != nil {
            defaults.removeObject(forKey: Self.pendingRecallsKey)
        }
    }

    private func persistPendingRecallsAndVerify(expectedRunID: String) throws {
        try persistPendingRecalls()
        let readBackData = try Data(contentsOf: pendingRecallsFileURL)
        let verifiedRecords = try decoder.decode([PendingRecall].self, from: readBackData)
        guard verifiedRecords.contains(where: { $0.runID == expectedRunID }) else {
            throw FounderAppError.invalidTrack("Pending recall read-back verification failed for \(expectedRunID)")
        }
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
