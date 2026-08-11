import CoreLocation
import CryptoKit
import Foundation

struct MissionConfig: Codable {
    let schemaVersion: String
    let missionID: String
    let title: String
    let subtitle: String
    let locationDisplayName: String
    let bindingID: String
    let bindingContractSHA256: String
    let bindingSHA256: String
    let snapshotSHA256: String
    let gpxPrefix: String
    let audioFile: String
    let audioSHA256: String
    let audioManifestSHA256: String
    let durationSeconds: TimeInterval
    let routeInitiallyApproved: Bool
    let workoutInitiallyApproved: Bool
    let m1HumanApprovalComplete: Bool
    let routePoints: [RoutePoint]
    let routeSHA256: String
    let timeline: [TimelineBlock]
    let timelineSHA256: String
    let evidenceNotice: String

    static func loadFromBundle(bundle: Bundle = .main) throws -> MissionConfig {
        guard let url = bundle.url(forResource: "mission", withExtension: "json") else {
            throw FounderAppError.missingResource("mission.json")
        }
        let mission = try JSONDecoder().decode(MissionConfig.self, from: Data(contentsOf: url))
        try mission.validate()

        guard let audioURL = mission.audioURL(in: bundle) else {
            throw FounderAppError.missingResource(mission.audioFile)
        }
        let actualSHA = try BundleIntegrity.sha256(of: audioURL)
        guard actualSHA.caseInsensitiveCompare(mission.audioSHA256) == .orderedSame else {
            throw FounderAppError.audioIntegrity(
                "SHA-256 master-аудио не совпадает с mission.json. Ожидался \(mission.audioSHA256), получен \(actualSHA)."
            )
        }
        let audioBaseName = URL(fileURLWithPath: mission.audioFile)
            .deletingPathExtension().lastPathComponent
        guard let manifestURL = bundle.url(
            forResource: "\(audioBaseName).manifest",
            withExtension: "json"
        ) else {
            throw FounderAppError.missingResource("\(audioBaseName).manifest.json")
        }
        let actualManifestSHA = try BundleIntegrity.sha256(of: manifestURL)
        guard actualManifestSHA.caseInsensitiveCompare(mission.audioManifestSHA256) == .orderedSame else {
            throw FounderAppError.audioIntegrity(
                "SHA-256 audio manifest не совпадает с mission.json."
            )
        }
        return mission
    }

    func audioURL(in bundle: Bundle = .main) -> URL? {
        let fileURL = URL(fileURLWithPath: audioFile)
        return bundle.url(
            forResource: fileURL.deletingPathExtension().lastPathComponent,
            withExtension: fileURL.pathExtension
        )
    }

    func validate() throws {
        var problems: [String] = []
        if schemaVersion != "0.1" { problems.append("неподдерживаемая schemaVersion \(schemaVersion)") }
        if missionID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { problems.append("пустой missionID") }
        if bindingID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { problems.append("пустой bindingID") }
        if gpxPrefix.isEmpty || gpxPrefix.range(of: "^[a-z0-9]+(?:-[a-z0-9]+)*$", options: .regularExpression) == nil {
            problems.append("gpxPrefix должен быть безопасным lowercase slug")
        }
        if audioFile.isEmpty || audioFile.contains("/") || audioFile.contains("\\") {
            problems.append("audioFile должен быть простым именем файла")
        }
        let shaPattern = try? NSRegularExpression(pattern: "^[0-9a-fA-F]{64}$")
        for (label, value) in [
            ("audioSHA256", audioSHA256),
            ("audioManifestSHA256", audioManifestSHA256),
            ("bindingSHA256", bindingSHA256),
            ("bindingContractSHA256", bindingContractSHA256),
            ("snapshotSHA256", snapshotSHA256),
            ("routeSHA256", routeSHA256),
            ("timelineSHA256", timelineSHA256),
        ] {
            let range = NSRange(value.startIndex..., in: value)
            if shaPattern?.firstMatch(in: value, range: range) == nil {
                problems.append("\(label) должен содержать 64 hex-символа")
            }
        }
        if !durationSeconds.isFinite || durationSeconds <= 0 {
            problems.append("durationSeconds должен быть положительным")
        }
        if routeInitiallyApproved != workoutInitiallyApproved
            || routeInitiallyApproved != m1HumanApprovalComplete {
            problems.append("initial approval flags должны иметь единое fail-closed значение")
        }
        if routePoints.count < 2 {
            problems.append("маршрут должен содержать минимум две точки")
        }
        if Set(routePoints.map(\.id)).count != routePoints.count {
            problems.append("route point id должны быть уникальными")
        }
        for point in routePoints where !point.hasValidCoordinate {
            problems.append("точка \(point.id) содержит недопустимые координаты")
        }
        if let first = routePoints.first, let last = routePoints.last,
           first.location.distance(from: last.location) > 25 {
            problems.append("founder route должен замыкаться в пределах 25 м")
        }

        if timeline.isEmpty {
            problems.append("timeline пуст")
        } else {
            let ordered = timeline.sorted { $0.start < $1.start }
            if abs((ordered.first?.start ?? -1) - 0) > 0.01 {
                problems.append("timeline должен начинаться в 0")
            }
            for (previous, current) in zip(ordered, ordered.dropFirst()) {
                if abs(previous.end - current.start) > 0.01 {
                    problems.append("timeline содержит gap/overlap между \(previous.end) и \(current.start)")
                }
            }
            if ordered.contains(where: { !$0.start.isFinite || !$0.end.isFinite || $0.end <= $0.start }) {
                problems.append("timeline содержит неположительный или нечисловой интервал")
            }
            if abs((ordered.last?.end ?? -1) - durationSeconds) > 0.5 {
                problems.append("timeline не заканчивается на durationSeconds")
            }
        }
        if !problems.isEmpty {
            throw FounderAppError.invalidMission(problems.joined(separator: "; "))
        }
        guard let actualRouteSHA = try? BundleIntegrity.canonicalSHA256(of: routePoints),
              actualRouteSHA.caseInsensitiveCompare(routeSHA256) == .orderedSame else {
            throw FounderAppError.invalidMission("routeSHA256 не совпадает с routePoints")
        }
        guard let actualTimelineSHA = try? BundleIntegrity.canonicalSHA256(of: timeline),
              actualTimelineSHA.caseInsensitiveCompare(timelineSHA256) == .orderedSame else {
            throw FounderAppError.invalidMission("timelineSHA256 не совпадает с timeline")
        }
    }

    var routeWorkoutFingerprint: String {
        let payload = RouteWorkoutFingerprint(
            schemaVersion: schemaVersion,
            missionID: missionID,
            bindingID: bindingID,
            bindingContractSHA256: bindingContractSHA256,
            gpxPrefix: gpxPrefix,
            durationSeconds: durationSeconds,
            routePoints: routePoints,
            timeline: timeline
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = (try? encoder.encode(payload)) ?? Data()
        return BundleIntegrity.sha256(of: data)
    }
}

private struct RouteWorkoutFingerprint: Codable {
    let schemaVersion: String
    let missionID: String
    let bindingID: String
    let bindingContractSHA256: String
    let gpxPrefix: String
    let durationSeconds: TimeInterval
    let routePoints: [RoutePoint]
    let timeline: [TimelineBlock]
}

enum BundleIntegrity {
    static func sha256(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 64 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    static func sha256(of data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    static func canonicalSHA256<T: Encodable>(of value: T) throws -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return sha256(of: try encoder.encode(value))
    }
}

struct RoutePoint: Codable, Identifiable, Hashable {
    let id: String
    let role: String
    let roleLabel: String
    let name: String
    let latitude: Double
    let longitude: Double
    let osmURL: URL

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    var location: CLLocation { CLLocation(latitude: latitude, longitude: longitude) }

    var hasValidCoordinate: Bool {
        latitude.isFinite && longitude.isFinite
            && (-90...90).contains(latitude) && (-180...180).contains(longitude)
    }
}

struct TimelineBlock: Codable, Identifiable, Equatable {
    var id: String { "\(start)-\(end)-\(kind)" }
    let start: TimeInterval
    let end: TimeInterval
    let label: String
    let kind: String
}

enum SessionMode: String, Codable {
    case walkthrough
    case mission
}

struct TrackSample: Codable, Identifiable, Equatable {
    let id: UUID
    let latitude: Double
    let longitude: Double
    let elevation: Double
    let horizontalAccuracy: Double
    let timestamp: Date

    init(location: CLLocation) {
        id = UUID()
        latitude = location.coordinate.latitude
        longitude = location.coordinate.longitude
        elevation = location.altitude
        horizontalAccuracy = location.horizontalAccuracy
        timestamp = location.timestamp
    }

    init(
        id: UUID = UUID(),
        latitude: Double,
        longitude: Double,
        elevation: Double,
        horizontalAccuracy: Double,
        timestamp: Date
    ) {
        self.id = id
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.horizontalAccuracy = horizontalAccuracy
        self.timestamp = timestamp
    }

    var location: CLLocation {
        CLLocation(
            coordinate: CLLocationCoordinate2D(latitude: latitude, longitude: longitude),
            altitude: elevation,
            horizontalAccuracy: horizontalAccuracy,
            verticalAccuracy: -1,
            timestamp: timestamp
        )
    }

    var isValid: Bool {
        latitude.isFinite && longitude.isFinite && elevation.isFinite && horizontalAccuracy.isFinite
            && (-90...90).contains(latitude) && (-180...180).contains(longitude)
            && horizontalAccuracy >= 0
    }
}

struct TrackSummary: Codable, Equatable {
    static let maximumEvidenceSampleGapSeconds: TimeInterval = 120

    let fileName: String
    let fileSHA256: String
    let sampleCount: Int
    let startedAt: Date
    let endedAt: Date
    let durationSeconds: TimeInterval
    let distanceMeters: Double
    let meanHorizontalAccuracyMeters: Double
    let maximumSampleGapSeconds: TimeInterval

    static func make(
        fileName: String,
        samples: [TrackSample],
        endedAt: Date = Date(),
        fileSHA256: String? = nil
    ) throws -> TrackSummary {
        let ordered = samples.sorted { $0.timestamp < $1.timestamp }
        guard URL(fileURLWithPath: fileName).lastPathComponent == fileName,
              !fileName.contains("/"),
              !fileName.contains("\\"),
              fileName.lowercased().hasSuffix(".gpx") else {
            throw FounderAppError.invalidTrack("GPX filename должен быть безопасным именем файла")
        }
        guard let first = ordered.first, let last = ordered.last else {
            throw FounderAppError.noRecordedTrack
        }
        guard ordered.allSatisfy(\.isValid) else {
            throw FounderAppError.invalidTrack("трек содержит недопустимую точку")
        }
        let gaps = zip(ordered, ordered.dropFirst()).map {
            $0.1.timestamp.timeIntervalSince($0.0.timestamp)
        }
        guard gaps.allSatisfy({ $0 > 0 }) else {
            throw FounderAppError.invalidTrack("GPS timestamps должны строго возрастать")
        }
        let distance = zip(ordered, ordered.dropFirst()).reduce(0.0) { partial, pair in
            partial + pair.0.location.distance(from: pair.1.location)
        }
        let meanAccuracy = ordered.map(\.horizontalAccuracy).reduce(0, +) / Double(ordered.count)
        let resolvedSHA = try fileSHA256
            ?? BundleIntegrity.sha256(of: GPXDocument.data(samples: ordered))
        guard Self.isValidSHA256(resolvedSHA) else {
            throw FounderAppError.invalidTrack("GPX SHA-256 имеет неверный формат")
        }
        return TrackSummary(
            fileName: fileName,
            fileSHA256: resolvedSHA.lowercased(),
            sampleCount: ordered.count,
            startedAt: first.timestamp,
            endedAt: max(endedAt, last.timestamp),
            durationSeconds: max(0, last.timestamp.timeIntervalSince(first.timestamp)),
            distanceMeters: distance,
            meanHorizontalAccuracyMeters: meanAccuracy,
            maximumSampleGapSeconds: gaps.max() ?? 0
        )
    }

    func isSufficientMissionEvidence(for mission: MissionConfig) -> Bool {
        Self.isValidSHA256(fileSHA256)
            && sampleCount >= 20
            && durationSeconds >= mission.durationSeconds - 30
            && distanceMeters >= 200
            && meanHorizontalAccuracyMeters <= 50
            && maximumSampleGapSeconds <= Self.maximumEvidenceSampleGapSeconds
    }

    static func isValidSHA256(_ value: String) -> Bool {
        value.range(of: "^[0-9a-fA-F]{64}$", options: .regularExpression) != nil
    }
}

struct WalkthroughEvidence: Codable, Equatable {
    let schemaVersion: String
    let bindingID: String
    let routeWorkoutFingerprint: String
    let approvedAt: Date
    let track: TrackSummary
    let startFinishClosureMeters: Double
    let startDistanceToPublicStartMeters: Double
    let finishDistanceToPublicStartMeters: Double
    let reachedRoutePointIDs: [String]
    let locationIncidents: [String]

    static let routePointRadiusMeters = 100.0
    static let minimumSamplesPerRoutePoint = 3

    static func make(
        mission: MissionConfig,
        summary: TrackSummary,
        samples: [TrackSample],
        locationIncidents: [String] = []
    ) -> WalkthroughEvidence {
        let orderedSamples = samples.sorted { $0.timestamp < $1.timestamp }
        var searchStart = 0
        var reached: [String] = []
        for point in mission.routePoints {
            var nearbyCount = 0
            var reachedAt: Int?
            for index in searchStart..<orderedSamples.count {
                if orderedSamples[index].location.distance(from: point.location) <= routePointRadiusMeters {
                    nearbyCount += 1
                    if nearbyCount >= minimumSamplesPerRoutePoint {
                        reachedAt = index
                        break
                    }
                }
            }
            guard let reachedAt else { break }
            reached.append(point.id)
            searchStart = reachedAt + 1
        }
        let publicStart = mission.routePoints.first?.location
        let closure = if let first = orderedSamples.first,
                         let last = orderedSamples.last {
            first.location.distance(from: last.location)
        } else {
            Double.infinity
        }
        let startDistance = if let first = orderedSamples.first, let publicStart {
            first.location.distance(from: publicStart)
        } else {
            Double.infinity
        }
        let finishDistance = if let last = orderedSamples.last, let publicStart {
            last.location.distance(from: publicStart)
        } else {
            Double.infinity
        }
        return WalkthroughEvidence(
            schemaVersion: "0.2",
            bindingID: mission.bindingID,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            approvedAt: Date(),
            track: summary,
            startFinishClosureMeters: closure,
            startDistanceToPublicStartMeters: startDistance,
            finishDistanceToPublicStartMeters: finishDistance,
            reachedRoutePointIDs: reached,
            locationIncidents: locationIncidents
        )
    }

    func isSufficient(for mission: MissionConfig) -> Bool {
        let expected = mission.routePoints.map(\.id)
        return bindingID == mission.bindingID
            && routeWorkoutFingerprint == mission.routeWorkoutFingerprint
            && schemaVersion == "0.2"
            && TrackSummary.isValidSHA256(track.fileSHA256)
            && track.sampleCount >= 20
            && track.durationSeconds >= 120
            && track.distanceMeters >= 200
            && track.meanHorizontalAccuracyMeters <= 50
            && track.maximumSampleGapSeconds <= TrackSummary.maximumEvidenceSampleGapSeconds
            && startFinishClosureMeters <= 150
            && startDistanceToPublicStartMeters <= Self.routePointRadiusMeters
            && finishDistanceToPublicStartMeters <= Self.routePointRadiusMeters
            && reachedRoutePointIDs == expected
            && locationIncidents.isEmpty
    }
}

struct AudioApprovalRecord: Codable, Equatable {
    let schemaVersion: String
    let audioSHA256: String
    let completedAt: Date
    let playbackDurationSeconds: TimeInterval
    let lockScreenConfirmed: Bool
    let controlsConfirmed: Bool
    let noCriticalIncidentsConfirmed: Bool

    func isValid(for mission: MissionConfig) -> Bool {
        schemaVersion == "0.2"
            && audioSHA256.caseInsensitiveCompare(mission.audioSHA256) == .orderedSame
            && playbackDurationSeconds >= mission.durationSeconds - 1
            && lockScreenConfirmed
            && controlsConfirmed
            && noCriticalIncidentsConfirmed
    }
}

struct RunSessionContext: Codable, Equatable {
    let participantID: String
    let runID: String
    let missionID: String
    let bindingID: String
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let condition: String
    let startedAt: Date
    let endedAt: Date
    let precommittedNextWorkoutAt: Date
    let completed: Bool
    let aborted: Bool
    let abortReason: String
    let audioElapsedSeconds: TimeInterval
    let pauseCount: Int
    let track: TrackSummary?
    let routeTraversalEvidence: WalkthroughEvidence?
    let audioIncidents: [String]
    let locationIncidents: [String]

    init(
        participantID: String = "participant_founder_default",
        runID: String,
        missionID: String,
        bindingID: String,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        condition: String,
        startedAt: Date,
        endedAt: Date,
        precommittedNextWorkoutAt: Date,
        completed: Bool,
        aborted: Bool,
        abortReason: String,
        audioElapsedSeconds: TimeInterval,
        pauseCount: Int,
        track: TrackSummary?,
        routeTraversalEvidence: WalkthroughEvidence?,
        audioIncidents: [String],
        locationIncidents: [String]
    ) {
        self.participantID = participantID
        self.runID = runID
        self.missionID = missionID
        self.bindingID = bindingID
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.condition = condition
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.precommittedNextWorkoutAt = precommittedNextWorkoutAt
        self.completed = completed
        self.aborted = aborted
        self.abortReason = abortReason
        self.audioElapsedSeconds = audioElapsedSeconds
        self.pauseCount = pauseCount
        self.track = track
        self.routeTraversalEvidence = routeTraversalEvidence
        self.audioIncidents = audioIncidents
        self.locationIncidents = locationIncidents
    }
}

struct DebriefRecord: Codable {
    let schemaVersion: String
    let recordStatus: String
    let participantID: String
    let runID: String
    let bindingID: String
    let missionID: String
    let condition: String
    let participantRole: String
    let startedAtLocal: Date
    let endedAtLocal: Date
    let recordedAtLocal: Date
    let recordingDelaySeconds: Double
    let precommittedNextWorkoutAtLocal: Date
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let track: TrackSummary?
    let routeTraversalEvidence: WalkthroughEvidence?
    let safety: SafetyEvidence
    let runtime: RuntimeEvidence
    let immediateDebriefBeforeEdits: ImmediateDebriefEvidence
    let recallAfter24h: RecallAfter24HoursEvidence
    let confounds: ConfoundEvidence
    let device: DeviceEvidence
    let evidenceLimits: [String]

    init(
        schemaVersion: String,
        recordStatus: String,
        participantID: String = "participant_founder_default",
        runID: String,
        bindingID: String,
        missionID: String,
        condition: String,
        participantRole: String,
        startedAtLocal: Date,
        endedAtLocal: Date,
        recordedAtLocal: Date,
        recordingDelaySeconds: Double,
        precommittedNextWorkoutAtLocal: Date,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        track: TrackSummary?,
        routeTraversalEvidence: WalkthroughEvidence?,
        safety: SafetyEvidence,
        runtime: RuntimeEvidence,
        immediateDebriefBeforeEdits: ImmediateDebriefEvidence,
        recallAfter24h: RecallAfter24HoursEvidence,
        confounds: ConfoundEvidence,
        device: DeviceEvidence,
        evidenceLimits: [String]
    ) {
        self.schemaVersion = schemaVersion
        self.recordStatus = recordStatus
        self.participantID = participantID
        self.runID = runID
        self.bindingID = bindingID
        self.missionID = missionID
        self.condition = condition
        self.participantRole = participantRole
        self.startedAtLocal = startedAtLocal
        self.endedAtLocal = endedAtLocal
        self.recordedAtLocal = recordedAtLocal
        self.recordingDelaySeconds = recordingDelaySeconds
        self.precommittedNextWorkoutAtLocal = precommittedNextWorkoutAtLocal
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.track = track
        self.routeTraversalEvidence = routeTraversalEvidence
        self.safety = safety
        self.runtime = runtime
        self.immediateDebriefBeforeEdits = immediateDebriefBeforeEdits
        self.recallAfter24h = recallAfter24h
        self.confounds = confounds
        self.device = device
        self.evidenceLimits = evidenceLimits
    }
}

struct SafetyEvidence: Codable {
    let routeManuallyChecked: Bool
    let abort: Bool
    let abortReason: String
    let neededScreenWhileMoving: Bool
    let navConflicts: [String]
}

struct RuntimeEvidence: Codable {
    let completed: Bool
    let geoSlotsReached: [String]
    let geoFallbacksUsed: [String]
    let missedOrLateCues: [String]
    let operatorImprovisationUsed: Bool
    let audioIncidents: [String]
    let additionalAudioNotes: String
    let offRouteIncidents: [String]
    let pauseCount: Int
    let locationIncidents: [String]
}

struct ImmediateDebriefEvidence: Codable {
    let missionGoalInOneSentence: String
    let momentCompanionBecameImportant: String
    let unaidedMemorableScene: String
    let attentionDropMoment: String
    let whatPhysicalMovementChanged: String
    let desireForM02_1To7: Int
    let placeNecessity1To7: Int
    let predictedNextTwist: String
    let nextWorkoutStillScheduled: Bool

    enum CodingKeys: String, CodingKey {
        case missionGoalInOneSentence = "mission_goal_in_one_sentence"
        case momentCompanionBecameImportant = "moment_companion_became_important"
        case unaidedMemorableScene = "unaided_memorable_scene"
        case attentionDropMoment = "attention_drop_moment"
        case whatPhysicalMovementChanged = "what_physical_movement_changed"
        case desireForM02_1To7 = "desire_for_m02_1_to_7"
        case placeNecessity1To7 = "place_necessity_1_to_7"
        case predictedNextTwist = "predicted_next_twist"
        case nextWorkoutStillScheduled = "next_workout_still_scheduled"
    }
}

struct RecallAfter24HoursEvidence: Codable {
    let pending: Bool
    let instructions: String
}

struct PendingRecall: Codable, Equatable, Identifiable {
    var id: String { runID }
    let participantID: String
    let runID: String
    let bindingID: String
    let missionID: String
    let condition: String
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let runEndedAt: Date
    let dueAt: Date

    init(
        participantID: String = "participant_founder_default",
        runID: String,
        bindingID: String,
        missionID: String,
        condition: String,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        runEndedAt: Date,
        dueAt: Date
    ) {
        self.participantID = participantID
        self.runID = runID
        self.bindingID = bindingID
        self.missionID = missionID
        self.condition = condition
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.runEndedAt = runEndedAt
        self.dueAt = dueAt
    }

    static func make(context: RunSessionContext) -> PendingRecall {
        PendingRecall(
            participantID: context.participantID,
            runID: context.runID,
            bindingID: context.bindingID,
            missionID: context.missionID,
            condition: context.condition,
            audioSHA256: context.audioSHA256,
            routeWorkoutFingerprint: context.routeWorkoutFingerprint,
            runEndedAt: context.endedAt,
            dueAt: context.endedAt.addingTimeInterval(24 * 60 * 60)
        )
    }
}

struct RecallCompletionRecord: Codable {
    let schemaVersion: String
    let recordStatus: String
    let participantID: String
    let runID: String
    let bindingID: String
    let missionID: String
    let condition: String
    let audioSHA256: String
    let routeWorkoutFingerprint: String
    let runEndedAtLocal: Date
    let dueAtLocal: Date
    let completedAtLocal: Date
    let unaidedStoryRecall: String
    let unaidedPlaceRecall: [String]
    let desireForM02_1To7: Int
    let evidenceLimits: [String]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case recordStatus = "record_status"
        case participantID = "participant_id"
        case runID = "run_id"
        case bindingID = "binding_id"
        case missionID = "mission_id"
        case condition
        case audioSHA256 = "audio_sha256"
        case routeWorkoutFingerprint = "route_workout_fingerprint"
        case runEndedAtLocal = "run_ended_at_local"
        case dueAtLocal = "due_at_local"
        case completedAtLocal = "completed_at_local"
        case unaidedStoryRecall = "unaided_story_recall"
        case unaidedPlaceRecall = "unaided_place_recall"
        case desireForM02_1To7 = "desire_for_m02_1_to_7"
        case evidenceLimits = "evidence_limits"
    }

    init(
        schemaVersion: String,
        recordStatus: String,
        participantID: String = "participant_founder_default",
        runID: String,
        bindingID: String,
        missionID: String,
        condition: String,
        audioSHA256: String,
        routeWorkoutFingerprint: String,
        runEndedAtLocal: Date,
        dueAtLocal: Date,
        completedAtLocal: Date,
        unaidedStoryRecall: String,
        unaidedPlaceRecall: [String],
        desireForM02_1To7: Int,
        evidenceLimits: [String]
    ) {
        self.schemaVersion = schemaVersion
        self.recordStatus = recordStatus
        self.participantID = participantID
        self.runID = runID
        self.bindingID = bindingID
        self.missionID = missionID
        self.condition = condition
        self.audioSHA256 = audioSHA256
        self.routeWorkoutFingerprint = routeWorkoutFingerprint
        self.runEndedAtLocal = runEndedAtLocal
        self.dueAtLocal = dueAtLocal
        self.completedAtLocal = completedAtLocal
        self.unaidedStoryRecall = unaidedStoryRecall
        self.unaidedPlaceRecall = unaidedPlaceRecall
        self.desireForM02_1To7 = desireForM02_1To7
        self.evidenceLimits = evidenceLimits
    }
}

struct ConfoundEvidence: Codable {
    let unfamiliarCityNovelty: String
    let fatigue: String
    let noise: String
    let weather: String
    let routeQuality: String
    let audioQuality: String
    let elevationOrStairs: String
}

struct DeviceEvidence: Codable {
    let model: String
    let systemName: String
    let systemVersion: String
    let headphones: String
    let lockScreenUsed: Bool
    let lockScreenAnswerRecorded: Bool
}

enum FounderAppError: LocalizedError {
    case missingResource(String)
    case invalidMission(String)
    case audioIntegrity(String)
    case noRecordedTrack
    case invalidTrack(String)

    var errorDescription: String? {
        switch self {
        case .missingResource(let name):
            return "Не найден локальный ресурс: \(name). Сначала подготовьте iOS bundle."
        case .invalidMission(let reason):
            return "Некорректный mission bundle: \(reason)."
        case .audioIntegrity(let reason):
            return "Master-аудио не прошло проверку целостности: \(reason)"
        case .noRecordedTrack:
            return "Маршрут ещё не записан."
        case .invalidTrack(let reason):
            return "GPX не может быть сохранён: \(reason)."
        }
    }
}

enum Formatters {
    static func clock(_ seconds: TimeInterval) -> String {
        let value = max(0, Int(seconds.rounded(.down)))
        return String(format: "%02d:%02d", value / 60, value % 60)
    }
}
