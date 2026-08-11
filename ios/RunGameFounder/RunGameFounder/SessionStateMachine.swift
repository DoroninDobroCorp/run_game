import Foundation

/// Pure state-machine component decoupling session lifecycle decisions from SwiftUI views.
struct SessionStateMachine: Equatable, Sendable {
    enum State: Equatable, Sendable {
        case ready
        case acquiringGPS(runID: String, startedAt: Date, qualifyingFixes: Int)
        case running(runID: String, startedAt: Date, runStartedAt: Date, pauseCount: Int, isPlaying: Bool)
        case completed(context: RunSessionContext)
        case aborted(context: RunSessionContext, reason: String)
    }

    enum Event: Equatable, Sendable {
        case requestStart(runID: String, now: Date)
        case receiveGPSFix(accuracy: Double, distanceToStartMeters: Double)
        case gpsFirstFixTimeout
        case gpsFailed(reason: String, elapsed: TimeInterval = 0, summary: TrackSummary? = nil, routeTraversal: WalkthroughEvidence? = nil)
        case audioStarted(now: Date = Date())
        case audioStartFailed(reason: String, elapsed: TimeInterval = 0, summary: TrackSummary? = nil, routeTraversal: WalkthroughEvidence? = nil)
        case pauseRequested
        case resumeRequested
        case audioInterrupted(reason: String, elapsed: TimeInterval, summary: TrackSummary? = nil, routeTraversal: WalkthroughEvidence? = nil)
        case routeDisconnected(elapsed: TimeInterval, summary: TrackSummary? = nil, routeTraversal: WalkthroughEvidence? = nil)
        case remoteStopRequested(elapsed: TimeInterval, summary: TrackSummary? = nil, routeTraversal: WalkthroughEvidence? = nil)
        case audioFinishedNaturally(
            summary: TrackSummary?,
            routeTraversal: WalkthroughEvidence?,
            audioIncidents: [String],
            locationIncidents: [String],
            elapsed: TimeInterval,
            now: Date = Date()
        )
        case userAborted(
            reason: String,
            summary: TrackSummary?,
            routeTraversal: WalkthroughEvidence?,
            audioIncidents: [String],
            locationIncidents: [String],
            elapsed: TimeInterval,
            now: Date = Date()
        )
        case processCrashRecovered(attempt: ActiveRunAttempt, endedAt: Date = Date())
    }

    enum Action: Equatable, Sendable {
        case startGPSRecording(prefix: String)
        case cancelGPSRecording
        case stopGPSRecording(completed: Bool)
        case startFirstFixTimer(seconds: TimeInterval)
        case cancelFirstFixTimer
        case startAudioPlayback
        case pauseAudioPlayback
        case stopAudioPlayback
        case saveJournal(ActiveRunAttempt)
        case clearJournal
        case scheduleDebrief(RunSessionContext)
        case scheduleRecall(RunSessionContext)
        case setStatusMessage(String?)
    }

    private(set) var state: State

    init(initialState: State = .ready) {
        self.state = initialState
    }

    var isReady: Bool {
        if case .ready = state { return true }
        return false
    }

    var isAcquiringGPS: Bool {
        if case .acquiringGPS = state { return true }
        return false
    }

    var isRunning: Bool {
        if case .running = state { return true }
        return false
    }

    var isCompleted: Bool {
        if case .completed = state { return true }
        return false
    }

    var isAborted: Bool {
        if case .aborted = state { return true }
        return false
    }

    mutating func handle(
        event: Event,
        mission: MissionConfig,
        precommittedNextWorkoutAt: Date
    ) -> [Action] {
        var actions: [Action] = []

        switch (state, event) {
        // MARK: - 1. GPS Acquisition
        case (.ready, .requestStart(let runID, let now)):
            state = .acquiringGPS(runID: runID, startedAt: now, qualifyingFixes: 0)
            let gpxPrefix = "\(mission.gpxPrefix)-run-\(runID)"
            let attempt = ActiveRunAttempt(
                runID: runID,
                missionID: mission.missionID,
                bindingID: mission.bindingID,
                audioSHA256: mission.audioSHA256,
                routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                partialGPXBasename: "\(gpxPrefix).partial.gpx",
                condition: "A",
                phase: .acquiringGPS,
                startedAt: now,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt,
                pauseCount: 0,
                audioIncidents: [],
                locationIncidents: []
            )
            actions.append(.saveJournal(attempt))
            actions.append(.startGPSRecording(prefix: gpxPrefix))
            actions.append(.startFirstFixTimer(seconds: 30))
            actions.append(.setStatusMessage(nil))

        case (.acquiringGPS(let runID, let startedAt, let count), .receiveGPSFix(let accuracy, let distance)):
            if accuracy > 35 {
                state = .acquiringGPS(runID: runID, startedAt: startedAt, qualifyingFixes: 0)
                actions.append(.setStatusMessage("GPS accuracy пока ±\(Int(accuracy)) м; ждём значение ≤35 м."))
            } else if distance > 100 {
                state = .acquiringGPS(runID: runID, startedAt: startedAt, qualifyingFixes: 0)
                actions.append(.setStatusMessage("Текущая позиция примерно в \(Int(distance)) м от публичного старта. Подойди к старту; аудио ещё не запущено."))
            } else {
                let newCount = count + 1
                if newCount < 2 {
                    state = .acquiringGPS(runID: runID, startedAt: startedAt, qualifyingFixes: newCount)
                    actions.append(.setStatusMessage("Получена 1 из 2 последовательных точных GPS-точек у старта…"))
                } else {
                    state = .acquiringGPS(runID: runID, startedAt: startedAt, qualifyingFixes: newCount)
                    actions.append(.cancelFirstFixTimer)
                    actions.append(.startAudioPlayback)
                }
            }

        case (.acquiringGPS(let runID, let startedAt, _), .audioStarted(let now)):
            state = .running(runID: runID, startedAt: startedAt, runStartedAt: now, pauseCount: 0, isPlaying: true)
            let gpxPrefix = "\(mission.gpxPrefix)-run-\(runID)"
            let attempt = ActiveRunAttempt(
                runID: runID,
                missionID: mission.missionID,
                bindingID: mission.bindingID,
                audioSHA256: mission.audioSHA256,
                routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                partialGPXBasename: "\(gpxPrefix).partial.gpx",
                condition: "A",
                phase: .running,
                startedAt: startedAt,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt,
                pauseCount: 0,
                audioIncidents: [],
                locationIncidents: []
            )
            actions.append(.saveJournal(attempt))
            actions.append(.setStatusMessage(nil))

        case (.acquiringGPS, .audioStartFailed(let reason, _, _, _)):
            state = .ready
            actions.append(.cancelFirstFixTimer)
            actions.append(.cancelGPSRecording)
            actions.append(.stopGPSRecording(completed: false))
            actions.append(.clearJournal)
            actions.append(.setStatusMessage(reason))

        case (.acquiringGPS, .gpsFirstFixTimeout):
            state = .ready
            actions.append(.cancelFirstFixTimer)
            actions.append(.cancelGPSRecording)
            actions.append(.stopGPSRecording(completed: false))
            actions.append(.clearJournal)
            actions.append(.setStatusMessage("За 30 секунд не получена точная GPS-точка у публичного старта."))

        case (.acquiringGPS, .gpsFailed(let reason, _, _, _)):
            state = .ready
            actions.append(.cancelFirstFixTimer)
            actions.append(.cancelGPSRecording)
            actions.append(.stopGPSRecording(completed: false))
            actions.append(.clearJournal)
            actions.append(.setStatusMessage(reason))

        // MARK: - 2. Running State & Actions
        case (.running(let runID, let startedAt, let runStartedAt, let pauseCount, let isPlaying), .pauseRequested):
            if isPlaying {
                let newPauseCount = pauseCount + 1
                state = .running(runID: runID, startedAt: startedAt, runStartedAt: runStartedAt, pauseCount: newPauseCount, isPlaying: false)
                actions.append(.pauseAudioPlayback)
            }

        case (.running(let runID, let startedAt, let runStartedAt, let pauseCount, let isPlaying), .resumeRequested):
            if !isPlaying {
                state = .running(runID: runID, startedAt: startedAt, runStartedAt: runStartedAt, pauseCount: pauseCount, isPlaying: true)
                actions.append(.startAudioPlayback)
            }

        case (.running, .audioInterrupted(let reason, let elapsed, let summary, let routeTraversal)):
            actions.append(contentsOf: handleAbort(
                reason: "Audio session interrupted: \(reason)",
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: [reason],
                locationIncidents: [],
                elapsed: elapsed,
                now: Date(),
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        case (.running, .routeDisconnected(let elapsed, let summary, let routeTraversal)):
            actions.append(contentsOf: handleAbort(
                reason: "Audio session interrupted: Headphones disconnected",
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: ["Headphones disconnected"],
                locationIncidents: [],
                elapsed: elapsed,
                now: Date(),
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        case (.running, .remoteStopRequested(let elapsed, let summary, let routeTraversal)):
            actions.append(contentsOf: handleAbort(
                reason: "Remote stop from lock-screen controls",
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: ["Remote stop requested"],
                locationIncidents: [],
                elapsed: elapsed,
                now: Date(),
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        case (.running, .gpsFailed(let reason, let elapsed, let summary, let routeTraversal)):
            actions.append(contentsOf: handleAbort(
                reason: "GPS session failed: \(reason)",
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: [],
                locationIncidents: [reason],
                elapsed: elapsed,
                now: Date(),
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        case (.running, .audioStartFailed(let reason, let elapsed, let summary, let routeTraversal)):
            actions.append(contentsOf: handleAbort(
                reason: "Fatal audio error: \(reason)",
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: [reason],
                locationIncidents: [],
                elapsed: elapsed,
                now: Date(),
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        // MARK: - 3. Natural Finish & User Abort
        case (.running(let runID, let startedAt, _, let pauseCount, _), .audioFinishedNaturally(let summary, let routeTraversal, let audioIncidents, let locationIncidents, let elapsed, let now)):
            actions.append(.cancelFirstFixTimer)
            actions.append(.stopGPSRecording(completed: true))

            let successful = summary?.isSufficientMissionEvidence(for: mission) == true
                && routeTraversal?.isSufficient(for: mission) == true
                && audioIncidents.isEmpty
                && locationIncidents.isEmpty

            var failureReasons: [String] = []
            if summary?.isSufficientMissionEvidence(for: mission) != true {
                failureReasons.append("GPX is missing or too short for the full mission")
            }
            if routeTraversal?.isSufficient(for: mission) != true {
                failureReasons.append("ordered route traversal or public start/finish evidence is incomplete")
            }
            if !audioIncidents.isEmpty { failureReasons.append("audio incident recorded") }
            if !locationIncidents.isEmpty { failureReasons.append("location incident recorded") }

            let context = RunSessionContext(
                runID: runID,
                missionID: mission.missionID,
                bindingID: mission.bindingID,
                audioSHA256: mission.audioSHA256,
                routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                condition: "A",
                startedAt: startedAt,
                endedAt: now,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt,
                completed: successful,
                aborted: !successful,
                abortReason: successful ? "" : failureReasons.joined(separator: "; "),
                audioElapsedSeconds: elapsed,
                pauseCount: pauseCount,
                track: summary,
                routeTraversalEvidence: routeTraversal,
                audioIncidents: audioIncidents,
                locationIncidents: locationIncidents
            )

            actions.append(.scheduleDebrief(context))
            actions.append(.clearJournal)
            if successful {
                actions.append(.scheduleRecall(context))
                state = .completed(context: context)
            } else {
                state = .aborted(context: context, reason: context.abortReason)
            }

        case (.running, .userAborted(let reason, let summary, let routeTraversal, let audioIncidents, let locationIncidents, let elapsed, let now)):
            actions.append(contentsOf: handleAbort(
                reason: reason,
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: audioIncidents,
                locationIncidents: locationIncidents,
                elapsed: elapsed,
                now: now,
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        case (.acquiringGPS, .userAborted(let reason, let summary, let routeTraversal, let audioIncidents, let locationIncidents, let elapsed, let now)):
            actions.append(contentsOf: handleAbort(
                reason: reason,
                summary: summary,
                routeTraversal: routeTraversal,
                audioIncidents: audioIncidents,
                locationIncidents: locationIncidents,
                elapsed: elapsed,
                now: now,
                mission: mission,
                precommittedNextWorkoutAt: precommittedNextWorkoutAt
            ))

        // MARK: - 4. Crash Recovery
        case (_, .processCrashRecovered(let attempt, let endedAt)):
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
            state = .aborted(context: recoveredContext, reason: recoveredContext.abortReason)
            actions.append(.scheduleDebrief(recoveredContext))
            actions.append(.clearJournal)

        // MARK: - 5. Callback Race Conditions / Out of order events
        default:
            break
        }

        return actions
    }

    private mutating func handleAbort(
        reason: String,
        summary: TrackSummary?,
        routeTraversal: WalkthroughEvidence?,
        audioIncidents: [String],
        locationIncidents: [String],
        elapsed: TimeInterval,
        now: Date,
        mission: MissionConfig,
        precommittedNextWorkoutAt: Date
    ) -> [Action] {
        var actions: [Action] = []
        actions.append(.cancelFirstFixTimer)
        actions.append(.stopAudioPlayback)
        actions.append(.stopGPSRecording(completed: false))

        let runID: String
        let startedAt: Date
        let pauseCount: Int

        switch state {
        case .acquiringGPS(let rID, let sAt, _):
            runID = rID
            startedAt = sAt
            pauseCount = 0
        case .running(let rID, let sAt, _, let pCount, _):
            runID = rID
            startedAt = sAt
            pauseCount = pCount
        default:
            return []
        }

        let context = RunSessionContext(
            runID: runID,
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: startedAt,
            endedAt: now,
            precommittedNextWorkoutAt: precommittedNextWorkoutAt,
            completed: false,
            aborted: true,
            abortReason: reason,
            audioElapsedSeconds: elapsed,
            pauseCount: pauseCount,
            track: summary,
            routeTraversalEvidence: routeTraversal,
            audioIncidents: audioIncidents,
            locationIncidents: locationIncidents
        )

        state = .aborted(context: context, reason: reason)
        actions.append(.scheduleDebrief(context))
        actions.append(.clearJournal)
        actions.append(.setStatusMessage(reason))
        return actions
    }
}
