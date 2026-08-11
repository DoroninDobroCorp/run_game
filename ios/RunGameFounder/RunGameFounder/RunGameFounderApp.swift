import SwiftUI

@main
struct RunGameFounderApp: App {
    @StateObject private var appModel: AppModel

    init() {
        if ProcessInfo.processInfo.arguments.contains("--ui-testing-reset") {
            let bundleID = Bundle.main.bundleIdentifier ?? "com.doronindobro.rungame.founder"
            UserDefaults.standard.removePersistentDomain(forName: bundleID)
        }
        let model = AppModel()
        if ProcessInfo.processInfo.arguments.contains("--ui-testing-pending-debrief") {
            if let mission = model.mission {
                let context = RunSessionContext(
                    participantID: model.participantId,
                    runID: "ui-test-debrief-1",
                    missionID: mission.missionID,
                    bindingID: mission.bindingID,
                    audioSHA256: mission.audioSHA256,
                    routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                    condition: "A",
                    startedAt: Date().addingTimeInterval(-1800),
                    endedAt: Date(),
                    precommittedNextWorkoutAt: Date().addingTimeInterval(86400),
                    completed: true,
                    aborted: false,
                    abortReason: "",
                    audioElapsedSeconds: 1800,
                    pauseCount: 0,
                    track: nil,
                    routeTraversalEvidence: nil,
                    audioIncidents: [],
                    locationIncidents: []
                )
                try? model.scheduleDebrief(for: context)
            }
        }
        if ProcessInfo.processInfo.arguments.contains("--ui-testing-pending-recall") {
            if let mission = model.mission {
                let context = RunSessionContext(
                    participantID: model.participantId,
                    runID: "ui-test-recall-1",
                    missionID: mission.missionID,
                    bindingID: mission.bindingID,
                    audioSHA256: mission.audioSHA256,
                    routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
                    condition: "A",
                    startedAt: Date().addingTimeInterval(-86400 * 2),
                    endedAt: Date().addingTimeInterval(-86400),
                    precommittedNextWorkoutAt: Date().addingTimeInterval(86400),
                    completed: true,
                    aborted: false,
                    abortReason: "",
                    audioElapsedSeconds: 1800,
                    pauseCount: 0,
                    track: nil,
                    routeTraversalEvidence: nil,
                    audioIncidents: [],
                    locationIncidents: []
                )
                try? model.scheduleRecall(for: context)
            }
        }
        _appModel = StateObject(wrappedValue: model)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appModel)
                .preferredColorScheme(.dark)
        }
    }
}
