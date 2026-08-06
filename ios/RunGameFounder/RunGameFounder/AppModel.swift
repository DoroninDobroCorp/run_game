import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var mission: MissionConfig?
    @Published private(set) var loadError: String?
    @Published var sidewalksChecked = false
    @Published var crossingsChecked = false
    @Published var elevationChecked = false
    @Published var screenFreeChecked = false
    @Published private(set) var routeApproved: Bool
    @Published private(set) var homeAudioCompleted: Bool

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        do {
            let loadedMission = try MissionConfig.loadFromBundle()
            mission = loadedMission
            loadError = nil
            routeApproved = defaults.bool(forKey: Self.routeApprovalKey(for: loadedMission))
                || (loadedMission.routeInitiallyApproved && loadedMission.workoutInitiallyApproved)
            homeAudioCompleted = defaults.bool(forKey: Self.audioApprovalKey(for: loadedMission))
        } catch {
            mission = nil
            loadError = error.localizedDescription
            routeApproved = false
            homeAudioCompleted = false
        }
    }

    var checklistComplete: Bool {
        sidewalksChecked && crossingsChecked && elevationChecked && screenFreeChecked
    }

    var canStartMission: Bool {
        routeApproved && homeAudioCompleted
    }

    var readinessCompletedSteps: Int {
        [mission != nil, routeApproved, homeAudioCompleted].filter { $0 }.count
    }

    func loadMission() {
        do {
            mission = try MissionConfig.loadFromBundle()
            guard let mission else { return }
            routeApproved = defaults.bool(forKey: Self.routeApprovalKey(for: mission))
                || (mission.routeInitiallyApproved && mission.workoutInitiallyApproved)
            homeAudioCompleted = defaults.bool(forKey: Self.audioApprovalKey(for: mission))
        } catch {
            loadError = error.localizedDescription
        }
    }

    func approveRoute() {
        guard checklistComplete else { return }
        routeApproved = true
        if let mission { defaults.set(true, forKey: Self.routeApprovalKey(for: mission)) }
    }

    func markHomeAudioCompleted() {
        homeAudioCompleted = true
        if let mission { defaults.set(true, forKey: Self.audioApprovalKey(for: mission)) }
    }

    func resetLocalApprovals() {
        routeApproved = false
        homeAudioCompleted = false
        sidewalksChecked = false
        crossingsChecked = false
        elevationChecked = false
        screenFreeChecked = false
        if let mission {
            defaults.removeObject(forKey: Self.routeApprovalKey(for: mission))
            defaults.removeObject(forKey: Self.audioApprovalKey(for: mission))
        }
    }

    func timelineBlock(at elapsed: TimeInterval) -> TimelineBlock? {
        mission?.timeline.last(where: { elapsed >= $0.start && elapsed < $0.end })
    }

    private static func routeApprovalKey(for mission: MissionConfig) -> String {
        "founder.routeApproved.\(mission.bindingID)"
    }

    private static func audioApprovalKey(for mission: MissionConfig) -> String {
        "founder.homeAudioCompleted.\(mission.audioSHA256)"
    }
}
