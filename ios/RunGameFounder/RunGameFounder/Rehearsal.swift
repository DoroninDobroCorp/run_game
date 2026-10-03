import Foundation

/// A rehearsal never owns a LocationRecorder, AppModel, research journal or approval.
/// It exercises the same session state machine with explicitly simulated input.
@MainActor
final class Rehearsal: ObservableObject {
    @Published private(set) var elapsed: TimeInterval = 0
    @Published private(set) var isPlaying = false
    @Published private(set) var report: RehearsalReport?
    @Published private(set) var errorMessage: String?
    @Published private(set) var reportURL: URL?
    let mission: MissionConfig
    private(set) var stateMachine = SessionStateMachine()
    private var startedAt = Date()

    init(mission: MissionConfig) { self.mission = mission }

    var currentBlock: TimelineBlock? {
        mission.timeline.first { elapsed >= $0.start && elapsed < $0.end }
    }

    var progress: Double { min(1, max(0, elapsed / mission.durationSeconds)) }
    var routeProgress: Double { Self.routeProgress(at: elapsed, mission: mission) }

    static func routeProgress(at elapsed: TimeInterval, mission: MissionConfig) -> Double {
        func effort(until time: TimeInterval) -> Double {
            mission.timeline.reduce(0) { sum, block in
                let seconds = max(0, min(time, block.end) - block.start)
                return sum + seconds * (block.kind == "run" ? 2.0 : 1.3)
            }
        }
        let total = effort(until: mission.durationSeconds)
        return total > 0 ? min(1, max(0, effort(until: elapsed) / total)) : 0
    }

    func play() {
        guard report == nil, mission.offlineRoute != nil else { return }
        if stateMachine.isReady {
            startedAt = Date()
            handle(.requestStart(runID: "simulation-" + UUID().uuidString.lowercased(), now: startedAt))
            handle(.receiveGPSFix(accuracy: 5, distanceToStartMeters: 0))
            handle(.receiveGPSFix(accuracy: 5, distanceToStartMeters: 0))
            handle(.audioStarted(now: startedAt))
        } else {
            handle(.resumeRequested)
        }
        isPlaying = stateMachine.isRunning
    }

    func pause() {
        guard isPlaying else { return }
        handle(.pauseRequested)
        isPlaying = false
    }

    func advance(by seconds: TimeInterval) {
        guard isPlaying, seconds.isFinite, seconds > 0 else { return }
        elapsed = min(mission.durationSeconds, elapsed + seconds)
        if elapsed >= mission.durationSeconds { finish() }
    }

    func reset() {
        isPlaying = false
        elapsed = 0
        report = nil
        reportURL = nil
        errorMessage = nil
        stateMachine = SessionStateMachine()
    }

    func saveReport(directory: URL? = nil) {
        guard let report, reportURL == nil else { return }
        do {
            let destination = directory ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = destination.appendingPathComponent("simulation-\(UUID().uuidString.lowercased()).json")
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            encoder.dateEncodingStrategy = .iso8601
            try FileDurability.writeAtomicStaging(data: encoder.encode(report), to: url, overwrite: false)
            reportURL = url
            errorMessage = nil
        } catch {
            errorMessage = "Не удалось сохранить отчёт. Проверь свободное место и нажми «Сохранить результат теста» ещё раз, пока этот экран открыт."
        }
    }

    private func handle(_ event: SessionStateMachine.Event) {
        // Deliberately do not execute hardware/persistence actions from the research engine.
        _ = stateMachine.handle(event: event, mission: mission,
            precommittedNextWorkoutAt: startedAt.addingTimeInterval(172_800), participantID: "simulation-only")
    }

    private func finish() {
        isPlaying = false
        guard let route = mission.offlineRoute else { return }
        do {
            try mission.validate()
            let count = Int(mission.durationSeconds / 2)
            let samples: [TrackSample] = (0...count).compactMap { index in
                let seconds = min(Double(index) * 2, mission.durationSeconds)
                guard let point = route.coordinate(at: Self.routeProgress(at: seconds, mission: mission)) else { return nil }
                return TrackSample(latitude: point.latitude, longitude: point.longitude, elevation: 0,
                    horizontalAccuracy: 5, timestamp: startedAt.addingTimeInterval(seconds))
            }
            let end = startedAt.addingTimeInterval(mission.durationSeconds)
            let summary = try TrackSummary.make(fileName: "simulation-not-field-evidence.gpx", samples: samples, endedAt: end)
            let traversal = WalkthroughEvidence.make(mission: mission, summary: summary, samples: samples)
            handle(.audioFinishedNaturally(summary: summary, routeTraversal: traversal,
                audioIncidents: [], locationIncidents: [], elapsed: elapsed, now: end))
            report = RehearsalReport(
                schema: "run_game_rehearsal/1", simulated: true, fieldEvidence: false,
                createdAt: Date(), missionID: mission.missionID, bindingID: mission.bindingID,
                routeSHA256: mission.offlineRouteSHA256 ?? "", durationSeconds: elapsed,
                plannedDistanceMeters: route.distanceMeters, sampleCount: samples.count,
                visitedWaypoints: traversal.reachedRoutePointIDs.count, totalWaypoints: mission.routePoints.count,
                intervalsCompleted: mission.timeline.filter { $0.kind == "run" }.count,
                sessionCompleted: stateMachine.isCompleted, audioPlaybackVerified: false,
                notice: "Simulated positions and audio completion. No physical GPS, audio playback, route safety, or human approvals were verified."
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct RehearsalReport: Codable {
    let schema: String
    let simulated: Bool
    let fieldEvidence: Bool
    let createdAt: Date
    let missionID: String
    let bindingID: String
    let routeSHA256: String
    let durationSeconds: Double
    let plannedDistanceMeters: Double
    let sampleCount: Int
    let visitedWaypoints: Int
    let totalWaypoints: Int
    let intervalsCompleted: Int
    let sessionCompleted: Bool
    let audioPlaybackVerified: Bool
    let notice: String
}
