import SwiftUI

@main
struct RunGameFounderApp: App {
    @StateObject private var appModel: AppModel

    init() {
        if ProcessInfo.processInfo.arguments.contains("--ui-testing-reset") {
            let bundleID = Bundle.main.bundleIdentifier ?? "com.doronindobro.rungame.founder"
            UserDefaults.standard.removePersistentDomain(forName: bundleID)
        }
        _appModel = StateObject(wrappedValue: AppModel())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appModel)
                .preferredColorScheme(.dark)
        }
    }
}
