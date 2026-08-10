import Foundation

@MainActor
final class AppModel: ObservableObject {
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

    init(defaults: UserDefaults = .standard, documentsDirectory: URL? = nil) {
        self.defaults = defaults
        self.documentsDirectory = documentsDirectory
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
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
        )
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
        recoveredTrackURLs = urls
            .filter { $0.lastPathComponent.hasSuffix(".partial.gpx") }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        localEvidenceURLs = urls
            .filter {
                !$0.lastPathComponent.hasSuffix(".partial.gpx")
                    && ["gpx", "json"].contains($0.pathExtension.lowercased())
            }
            .sorted {
                let left = (try? $0.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
                let right = (try? $1.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
                return (left ?? .distantPast) > (right ?? .distantPast)
            }
    }

    func scheduleRecall(for context: RunSessionContext) {
        let pending = PendingRecall.make(context: context)
        pendingRecalls.removeAll { $0.runID == pending.runID }
        pendingRecalls.append(pending)
        pendingRecalls.sort { $0.dueAt < $1.dueAt }
        persistPendingRecalls()
    }

    func scheduleDebrief(for context: RunSessionContext) {
        pendingDebriefs.removeAll { $0.runID == context.runID }
        pendingDebriefs.append(context)
        pendingDebriefs.sort { $0.endedAt < $1.endedAt }
        persistPendingDebriefs()
    }

    func completeDebrief(runID: String) {
        pendingDebriefs.removeAll { $0.runID == runID }
        persistPendingDebriefs()
    }

    func completeRecall(runID: String) {
        pendingRecalls.removeAll { $0.runID == runID }
        persistPendingRecalls()
    }

    func saveActiveAttempt(_ attempt: ActiveRunAttempt) {
        ActiveRunJournal(defaults: defaults).save(attempt)
    }

    func clearActiveJournal() {
        ActiveRunJournal(defaults: defaults).clear()
    }

    func recoverActiveJournal() {
        let journal = ActiveRunJournal(defaults: defaults)
        switch journal.loadJournal() {
        case .attempt(let attempt):
            let endedAt = Date()
            let recoveredContext = RunSessionContext(
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
                audioElapsedSeconds: 0,
                pauseCount: attempt.pauseCount,
                track: nil,
                routeTraversalEvidence: nil,
                audioIncidents: attempt.audioIncidents + ["Interrupted by unexpected process termination"],
                locationIncidents: attempt.locationIncidents
            )
            scheduleDebrief(for: recoveredContext)
            journal.clear()
            journalCorrupted = false
            journalErrorBanner = nil
        case .corrupted(let reason):
            journalCorrupted = true
            journalErrorBanner = "Corrupted active run journal: \(reason). Evidence capture is locked."
        case .none:
            journalCorrupted = false
            journalErrorBanner = nil
        }
    }

    private func restorePendingRecalls() {
        guard let data = defaults.data(forKey: Self.pendingRecallsKey) else {
            pendingRecalls = []
            return
        }
        do {
            let records = try decoder.decode([PendingRecall].self, from: data)
            pendingRecalls = Dictionary(grouping: records, by: \.runID)
                .compactMap { $0.value.last }
                .sorted { $0.dueAt < $1.dueAt }
        } catch {
            queueCorrupted = true
            pendingRecalls = []
        }
    }

    private func restorePendingDebriefs() {
        guard let data = defaults.data(forKey: Self.pendingDebriefsKey) else {
            pendingDebriefs = []
            return
        }
        do {
            let records = try decoder.decode([RunSessionContext].self, from: data)
            pendingDebriefs = Dictionary(grouping: records, by: \.runID)
                .compactMap { $0.value.last }
                .sorted { $0.endedAt < $1.endedAt }
        } catch {
            queueCorrupted = true
            pendingDebriefs = []
        }
    }

    private func persistPendingDebriefs() {
        if let data = try? encoder.encode(pendingDebriefs) {
            defaults.set(data, forKey: Self.pendingDebriefsKey)
        }
    }

    private func persistPendingRecalls() {
        if let data = try? encoder.encode(pendingRecalls) {
            defaults.set(data, forKey: Self.pendingRecallsKey)
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
        guard let actualSHA = try? BundleIntegrity.sha256(of: url) else { return false }
        return actualSHA.caseInsensitiveCompare(track.fileSHA256) == .orderedSame
    }

    private static let routeApprovalPrefix = "founder.v2.routeApproved."
    private static let audioApprovalPrefix = "founder.v2.homeAudioCompleted."
    private static let pendingWalkthroughPrefix = "founder.v2.pendingWalkthrough."
    private static let pendingRecallsKey = "founder.v2.pendingRecalls"
    private static let pendingDebriefsKey = "founder.v2.pendingDebriefs"
}
