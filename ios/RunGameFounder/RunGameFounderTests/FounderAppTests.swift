import CoreLocation
import XCTest
@testable import RunGameFounder

@MainActor
final class FounderAppTests: XCTestCase {
    func testPendingEvidenceQueuesBlockAnotherMission() {
        XCTAssertTrue(
            AppModel.canBeginMission(
                readinessComplete: true,
                hasPendingDebrief: false,
                hasPendingRecall: false
            )
        )
        XCTAssertFalse(
            AppModel.canBeginMission(
                readinessComplete: true,
                hasPendingDebrief: true,
                hasPendingRecall: false
            )
        )
        XCTAssertFalse(
            AppModel.canBeginMission(
                readinessComplete: true,
                hasPendingDebrief: false,
                hasPendingRecall: true
            )
        )
    }

    func testClockFormatting() {
        XCTAssertEqual(Formatters.clock(0), "00:00")
        XCTAssertEqual(Formatters.clock(365.9), "06:05")
        XCTAssertEqual(Formatters.clock(1800), "30:00")
    }

    func testBundledMissionAndAudioIntegrityValidate() throws {
        let mission = try MissionConfig.loadFromBundle()
        XCTAssertEqual(mission.missionID, "m01")
        XCTAssertEqual(mission.routePoints.count, 5)
        XCTAssertFalse(mission.gpxPrefix.isEmpty)
        XCTAssertEqual(mission.audioSHA256.count, 64)
        XCTAssertNoThrow(try mission.validate())
    }

    func testSHA256KnownVector() {
        XCTAssertEqual(
            BundleIntegrity.sha256(of: Data("abc".utf8)),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
    }

    @MainActor
    func testAudioPauseCountOnlyCountsPlayingToPausedTransitions() {
        XCTAssertEqual(AudioController.pauseCount(after: 0, wasPlaying: true), 1)
        XCTAssertEqual(AudioController.pauseCount(after: 1, wasPlaying: false), 1)
    }

    func testRouteFingerprintChangesWithCoordinate() throws {
        let original = try MissionConfig.loadFromBundle()
        let changed = try decodedMission { object in
            var points = object["routePoints"] as! [[String: Any]]
            points[1]["latitude"] = (points[1]["latitude"] as! Double) + 0.0001
            object["routePoints"] = points
        }
        XCTAssertNotEqual(original.routeWorkoutFingerprint, changed.routeWorkoutFingerprint)
        XCTAssertThrowsError(try changed.validate())

        let changedBindingContract = try decodedMission {
            $0["bindingContractSHA256"] = String(repeating: "0", count: 64)
        }
        XCTAssertNotEqual(
            original.routeWorkoutFingerprint,
            changedBindingContract.routeWorkoutFingerprint
        )
    }

    func testMissionValidationRejectsEmptyRoute() throws {
        let mission = try decodedMission { $0["routePoints"] = [] }
        XCTAssertThrowsError(try mission.validate())

        let inconsistentApprovals = try decodedMission {
            $0["m1HumanApprovalComplete"] = true
        }
        XCTAssertThrowsError(try inconsistentApprovals.validate())

        let staleTimelineHash = try decodedMission { object in
            var timeline = object["timeline"] as! [[String: Any]]
            timeline[0]["label"] = "Tampered"
            object["timeline"] = timeline
        }
        XCTAssertThrowsError(try staleTimelineHash.validate())
    }

    func testGPXContainsValidNamespacedExtensionWithoutUploadMetadata() throws {
        let samples = [
            TrackSample(
                latitude: -33.046,
                longitude: -71.619,
                elevation: 12,
                horizontalAccuracy: 5,
                timestamp: Date(timeIntervalSince1970: 1_700_000_000)
            ),
            TrackSample(
                latitude: -33.045,
                longitude: -71.618,
                elevation: 14,
                horizontalAccuracy: 4,
                timestamp: Date(timeIntervalSince1970: 1_700_000_010)
            ),
        ]
        let xml = String(decoding: try GPXDocument.data(samples: samples), as: UTF8.self)
        XCTAssertTrue(xml.contains("<trkpt"))
        XCTAssertTrue(xml.contains("xmlns:rg=\"urn:run-game:gpx:founder:0.2\""))
        XCTAssertTrue(xml.contains("<rg:horizontalAccuracy>"))
        XCTAssertTrue(xml.contains("lat=\"-33.0460000\""))
        XCTAssertFalse(xml.lowercased().contains("upload"))
        XCTAssertFalse(xml.lowercased().contains("email"))
    }

    func testGPXRejectsEmptyAndInvalidTracks() {
        XCTAssertThrowsError(try GPXDocument.data(samples: []))
        let invalid = TrackSample(
            latitude: .nan,
            longitude: 0,
            elevation: 0,
            horizontalAccuracy: 5,
            timestamp: Date()
        )
        XCTAssertThrowsError(try GPXDocument.data(samples: [invalid]))

        let timestamp = Date(timeIntervalSince1970: 1_700_000_000)
        let duplicateTimestamps = [
            TrackSample(latitude: 0, longitude: 0, elevation: 0, horizontalAccuracy: 5, timestamp: timestamp),
            TrackSample(latitude: 0, longitude: 0.0001, elevation: 0, horizontalAccuracy: 5, timestamp: timestamp),
        ]
        XCTAssertThrowsError(try GPXDocument.data(samples: duplicateTimestamps))
    }

    func testWalkthroughEvidenceRequiresFullLoop() throws {
        let mission = try MissionConfig.loadFromBundle()
        let completeSamples = trackSamples(for: mission)
        let summary = try TrackSummary.make(fileName: "walk.gpx", samples: completeSamples)
        XCTAssertTrue(TrackSummary.isValidSHA256(summary.fileSHA256))
        let complete = WalkthroughEvidence.make(mission: mission, summary: summary, samples: completeSamples)
        XCTAssertTrue(complete.isSufficient(for: mission))

        let incident = WalkthroughEvidence.make(
            mission: mission,
            summary: summary,
            samples: completeSamples,
            locationIncidents: ["Synthetic GPS failure"]
        )
        XCTAssertFalse(incident.isSufficient(for: mission))

        let incompleteSamples = Array(completeSamples.prefix(10))
        let incompleteSummary = try TrackSummary.make(fileName: "short.gpx", samples: incompleteSamples)
        let incomplete = WalkthroughEvidence.make(
            mission: mission,
            summary: incompleteSummary,
            samples: incompleteSamples
        )
        XCTAssertFalse(incomplete.isSufficient(for: mission))

        let base = Date(timeIntervalSince1970: 1_800_100_000)
        let start = mission.routePoints[0]
        let sparseSamples = (0..<25).map { index -> TrackSample in
            let sparsePoint: RoutePoint
            switch index {
            case 6: sparsePoint = mission.routePoints[1]
            case 12: sparsePoint = mission.routePoints[2]
            case 18: sparsePoint = mission.routePoints[3]
            default: sparsePoint = start
            }
            return TrackSample(
                latitude: sparsePoint.latitude,
                longitude: sparsePoint.longitude,
                elevation: 0,
                horizontalAccuracy: 5,
                timestamp: base.addingTimeInterval(Double(index * 10))
            )
        }
        let sparseSummary = try TrackSummary.make(fileName: "sparse.gpx", samples: sparseSamples)
        let sparse = WalkthroughEvidence.make(
            mission: mission,
            summary: sparseSummary,
            samples: sparseSamples
        )
        XCTAssertFalse(sparse.isSufficient(for: mission))

        let reorderedBase = Date(timeIntervalSince1970: 1_800_200_000)
        let outOfOrderPoints = [
            mission.routePoints[0],
            mission.routePoints[2],
            mission.routePoints[1],
            mission.routePoints[3],
            mission.routePoints[4],
        ]
        let outOfOrderSamples = outOfOrderPoints.enumerated().flatMap { pointIndex, point in
            (0..<5).map { repetition in
                TrackSample(
                    latitude: point.latitude,
                    longitude: point.longitude,
                    elevation: 0,
                    horizontalAccuracy: 5,
                    timestamp: reorderedBase.addingTimeInterval(Double((pointIndex * 5 + repetition) * 10))
                )
            }
        }
        let outOfOrderSummary = try TrackSummary.make(
            fileName: "out-of-order.gpx",
            samples: outOfOrderSamples
        )
        let outOfOrder = WalkthroughEvidence.make(
            mission: mission,
            summary: outOfOrderSummary,
            samples: outOfOrderSamples
        )
        XCTAssertFalse(outOfOrder.isSufficient(for: mission))

        let awayFromStart = WalkthroughEvidence(
            schemaVersion: complete.schemaVersion,
            bindingID: complete.bindingID,
            routeWorkoutFingerprint: complete.routeWorkoutFingerprint,
            approvedAt: complete.approvedAt,
            track: complete.track,
            startFinishClosureMeters: complete.startFinishClosureMeters,
            startDistanceToPublicStartMeters: WalkthroughEvidence.routePointRadiusMeters + 1,
            finishDistanceToPublicStartMeters: complete.finishDistanceToPublicStartMeters,
            reachedRoutePointIDs: complete.reachedRoutePointIDs,
            locationIncidents: []
        )
        XCTAssertFalse(awayFromStart.isSufficient(for: mission))
    }

    @MainActor
    func testMissionRequiresVersionedFounderChecksAndHumanBinding() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)

        XCTAssertFalse(model.canStartMission)
        let audioRecord = AudioApprovalRecord(
            schemaVersion: "0.2",
            audioSHA256: mission.audioSHA256,
            completedAt: Date(),
            playbackDurationSeconds: mission.durationSeconds,
            lockScreenConfirmed: true,
            controlsConfirmed: true,
            noCriticalIncidentsConfirmed: true
        )
        model.markHomeAudioCompleted(record: audioRecord)
        XCTAssertFalse(model.canStartMission)

        model.sidewalksChecked = true
        model.crossingsChecked = true
        model.elevationChecked = true
        model.screenFreeChecked = true
        let samples = trackSamples(for: mission)
        let summary = try TrackSummary.make(fileName: "walk.gpx", samples: samples)
        model.approveRoute(evidence: .make(mission: mission, summary: summary, samples: samples))
        XCTAssertFalse(mission.m1HumanApprovalComplete)
        XCTAssertFalse(model.canStartMission)

        let restored = AppModel(defaults: defaults)
        XCTAssertFalse(restored.canStartMission)
    }

    @MainActor
    func testIncompleteChecklistAndStaleFingerprintCannotApproveRoute() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        let samples = trackSamples(for: mission)
        let summary = try TrackSummary.make(fileName: "walk.gpx", samples: samples)
        let valid = WalkthroughEvidence.make(mission: mission, summary: summary, samples: samples)

        model.sidewalksChecked = true
        model.approveRoute(evidence: valid)
        XCTAssertFalse(model.routeApproved)

        model.crossingsChecked = true
        model.elevationChecked = true
        model.screenFreeChecked = true
        let stale = WalkthroughEvidence(
            schemaVersion: valid.schemaVersion,
            bindingID: valid.bindingID,
            routeWorkoutFingerprint: "stale",
            approvedAt: valid.approvedAt,
            track: valid.track,
            startFinishClosureMeters: valid.startFinishClosureMeters,
            startDistanceToPublicStartMeters: valid.startDistanceToPublicStartMeters,
            finishDistanceToPublicStartMeters: valid.finishDistanceToPublicStartMeters,
            reachedRoutePointIDs: valid.reachedRoutePointIDs,
            locationIncidents: valid.locationIncidents
        )
        model.approveRoute(evidence: stale)
        XCTAssertFalse(model.routeApproved)
    }

    @MainActor
    func testIncompleteAudioEvidenceCannotApprove() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(defaults: defaults)
        let mission = try XCTUnwrap(model.mission)
        let record = AudioApprovalRecord(
            schemaVersion: "0.2",
            audioSHA256: mission.audioSHA256,
            completedAt: Date(),
            playbackDurationSeconds: 10,
            lockScreenConfirmed: true,
            controlsConfirmed: true,
            noCriticalIncidentsConfirmed: true
        )
        model.markHomeAudioCompleted(record: record)
        XCTAssertFalse(model.homeAudioCompleted)
    }

    func testMissionEvidenceRejectsShortOrInaccurateTrack() throws {
        let mission = try MissionConfig.loadFromBundle()
        let valid = TrackSummary(
            fileName: "mission.gpx",
            fileSHA256: String(repeating: "a", count: 64),
            sampleCount: 100,
            startedAt: Date(timeIntervalSince1970: 1_800_000_000),
            endedAt: Date(timeIntervalSince1970: 1_800_001_800),
            durationSeconds: mission.durationSeconds - 10,
            distanceMeters: 2_500,
            meanHorizontalAccuracyMeters: 12,
            maximumSampleGapSeconds: 10
        )
        XCTAssertTrue(valid.isSufficientMissionEvidence(for: mission))

        let short = TrackSummary(
            fileName: valid.fileName,
            fileSHA256: valid.fileSHA256,
            sampleCount: 19,
            startedAt: valid.startedAt,
            endedAt: valid.endedAt,
            durationSeconds: valid.durationSeconds,
            distanceMeters: valid.distanceMeters,
            meanHorizontalAccuracyMeters: valid.meanHorizontalAccuracyMeters,
            maximumSampleGapSeconds: valid.maximumSampleGapSeconds
        )
        XCTAssertFalse(short.isSufficientMissionEvidence(for: mission))

        let inaccurate = TrackSummary(
            fileName: valid.fileName,
            fileSHA256: valid.fileSHA256,
            sampleCount: valid.sampleCount,
            startedAt: valid.startedAt,
            endedAt: valid.endedAt,
            durationSeconds: valid.durationSeconds,
            distanceMeters: valid.distanceMeters,
            meanHorizontalAccuracyMeters: 51,
            maximumSampleGapSeconds: valid.maximumSampleGapSeconds
        )
        XCTAssertFalse(inaccurate.isSufficientMissionEvidence(for: mission))

        let interrupted = TrackSummary(
            fileName: valid.fileName,
            fileSHA256: valid.fileSHA256,
            sampleCount: valid.sampleCount,
            startedAt: valid.startedAt,
            endedAt: valid.endedAt,
            durationSeconds: valid.durationSeconds,
            distanceMeters: valid.distanceMeters,
            meanHorizontalAccuracyMeters: valid.meanHorizontalAccuracyMeters,
            maximumSampleGapSeconds: TrackSummary.maximumEvidenceSampleGapSeconds + 1
        )
        XCTAssertFalse(interrupted.isSufficientMissionEvidence(for: mission))
    }

    @MainActor
    func testPendingRecallPersistsAndCompletesByRunID() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)
        let endedAt = Date(timeIntervalSince1970: 1_800_000_000)
        let context = RunSessionContext(
            runID: "recall-test-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-mission.durationSeconds),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(48 * 60 * 60),
            completed: true,
            aborted: false,
            abortReason: "",
            audioElapsedSeconds: mission.durationSeconds,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )

        try model.scheduleRecall(for: context)
        try model.scheduleRecall(for: context)
        XCTAssertEqual(model.pendingRecalls.count, 1)
        XCTAssertEqual(model.pendingRecalls[0].dueAt, endedAt.addingTimeInterval(24 * 60 * 60))

        let restored = AppModel(defaults: defaults, documentsDirectory: docDir)
        XCTAssertEqual(restored.pendingRecalls.map(\.runID), [context.runID])
        try restored.completeRecall(runID: context.runID)
        XCTAssertTrue(restored.pendingRecalls.isEmpty)
        XCTAssertTrue(AppModel(defaults: defaults, documentsDirectory: docDir).pendingRecalls.isEmpty)
    }

    @MainActor
    func testPendingDebriefPersistsAndCompletesByRunID() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let docDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: docDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: docDir) }

        let model = AppModel(defaults: defaults, documentsDirectory: docDir)
        let mission = try XCTUnwrap(model.mission)
        let endedAt = Date(timeIntervalSince1970: 1_800_000_000)
        let context = RunSessionContext(
            runID: "debrief-test-run",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            audioSHA256: mission.audioSHA256,
            routeWorkoutFingerprint: mission.routeWorkoutFingerprint,
            condition: "A",
            startedAt: endedAt.addingTimeInterval(-120),
            endedAt: endedAt,
            precommittedNextWorkoutAt: endedAt.addingTimeInterval(48 * 60 * 60),
            completed: false,
            aborted: true,
            abortReason: "Synthetic test abort",
            audioElapsedSeconds: 120,
            pauseCount: 0,
            track: nil,
            routeTraversalEvidence: nil,
            audioIncidents: [],
            locationIncidents: []
        )

        try model.scheduleDebrief(for: context)
        try model.scheduleDebrief(for: context)
        XCTAssertEqual(model.pendingDebriefs, [context])

        let restored = AppModel(defaults: defaults, documentsDirectory: docDir)
        XCTAssertEqual(restored.pendingDebriefs, [context])
        try restored.completeDebrief(runID: context.runID)
        XCTAssertTrue(restored.pendingDebriefs.isEmpty)
        XCTAssertTrue(AppModel(defaults: defaults, documentsDirectory: docDir).pendingDebriefs.isEmpty)
    }

    @MainActor
    func testPendingWalkthroughPersistsOnlyWithIntactGPX() throws {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }

        let model = AppModel(defaults: defaults, documentsDirectory: directory)
        let mission = try XCTUnwrap(model.mission)
        let samples = trackSamples(for: mission)
        let fileName = "pending-walk.gpx"
        let fileURL = directory.appendingPathComponent(fileName)
        try GPXDocument.data(samples: samples).write(to: fileURL)
        let summary = try TrackSummary.make(
            fileName: fileName,
            samples: samples,
            fileSHA256: try BundleIntegrity.sha256(of: fileURL)
        )
        let evidence = WalkthroughEvidence.make(
            mission: mission,
            summary: summary,
            samples: samples
        )

        model.recordPendingWalkthrough(evidence: evidence)
        XCTAssertEqual(model.pendingWalkthroughEvidence, evidence)
        XCTAssertEqual(
            AppModel(defaults: defaults, documentsDirectory: directory).pendingWalkthroughEvidence,
            evidence
        )

        try Data("tampered".utf8).write(to: fileURL)
        XCTAssertNil(
            AppModel(defaults: defaults, documentsDirectory: directory).pendingWalkthroughEvidence
        )
    }

    @MainActor
    func testResetClearsEveryHistoricalApprovalFingerprint() {
        let suiteName = "FounderAppTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }
        defaults.set(Data([1]), forKey: "founder.v2.routeApproved.old-route")
        defaults.set(Data([2]), forKey: "founder.v2.homeAudioCompleted.old-audio")
        defaults.set(Data([3]), forKey: "founder.v2.pendingWalkthrough.old-route")
        defaults.set(Data([4]), forKey: "unrelated.evidence.queue")

        AppModel(defaults: defaults).resetLocalApprovals()

        XCTAssertNil(defaults.data(forKey: "founder.v2.routeApproved.old-route"))
        XCTAssertNil(defaults.data(forKey: "founder.v2.homeAudioCompleted.old-audio"))
        XCTAssertNil(defaults.data(forKey: "founder.v2.pendingWalkthrough.old-route"))
        XCTAssertNotNil(defaults.data(forKey: "unrelated.evidence.queue"))
    }

    private func trackSamples(for mission: MissionConfig) -> [TrackSample] {
        let base = Date(timeIntervalSince1970: 1_800_000_000)
        var samples: [TrackSample] = []
        for (pointIndex, point) in mission.routePoints.enumerated() {
            for repetition in 0..<5 {
                let index = pointIndex * 5 + repetition
                samples.append(
                    TrackSample(
                        latitude: point.latitude,
                        longitude: point.longitude,
                        elevation: Double(pointIndex),
                        horizontalAccuracy: 5,
                        timestamp: base.addingTimeInterval(Double(index * 10))
                    )
                )
            }
        }
        return samples
    }

    private func decodedMission(mutate: (inout [String: Any]) -> Void) throws -> MissionConfig {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "mission", withExtension: "json"))
        var object = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        mutate(&object)
        let data = try JSONSerialization.data(withJSONObject: object)
        return try JSONDecoder().decode(MissionConfig.self, from: data)
    }

    func testHostSideSwiftToPythonBridge_SuccessfulPairAndAbortedDebriefValidatesWithExitCode0() throws {
        let repoRoot = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let validatorScript = repoRoot.appendingPathComponent("tools/r02_validate_evidence.py")
        XCTAssertTrue(FileManager.default.fileExists(atPath: validatorScript.path), "r02_validate_evidence.py must exist")

        let pythonPath: String = {
            if let envPython = ProcessInfo.processInfo.environment["PYTHON"],
               FileManager.default.isExecutableFile(atPath: envPython) {
                return envPython
            }
            if FileManager.default.isExecutableFile(atPath: "/usr/bin/python3") {
                return "/usr/bin/python3"
            }
            return "/usr/bin/python3"
        }()

        func runValidator(args: [String]) throws -> (exitCode: Int32, stdout: String, stderr: String) {
            guard let taskClass = NSClassFromString("NSTask") as? NSObject.Type else {
                XCTFail("NSTask class not found in runtime")
                return (-1, "", "NSTask unavailable")
            }
            let task = taskClass.init()
            task.setValue(pythonPath, forKey: "launchPath")
            task.setValue([validatorScript.path] + args, forKey: "arguments")

            guard let pipeClass = NSClassFromString("NSPipe") as? NSObject.Type else {
                XCTFail("NSPipe class not found in runtime")
                return (-1, "", "NSPipe unavailable")
            }
            let outPipe = pipeClass.init()
            let errPipe = pipeClass.init()
            task.setValue(outPipe, forKey: "standardOutput")
            task.setValue(errPipe, forKey: "standardError")

            task.perform(NSSelectorFromString("launch"))
            task.perform(NSSelectorFromString("waitUntilExit"))

            let exitCode = (task.value(forKey: "terminationStatus") as? Int32) ?? -1
            let outHandle = outPipe.value(forKey: "fileHandleForReading") as! FileHandle
            let errHandle = errPipe.value(forKey: "fileHandleForReading") as! FileHandle

            let outData = outHandle.readDataToEndOfFile()
            let errData = errHandle.readDataToEndOfFile()
            return (
                exitCode,
                String(data: outData, encoding: .utf8) ?? "",
                String(data: errData, encoding: .utf8) ?? ""
            )
        }

        let tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }

        // 1. Successful pair validation
        let endedAt = Date(timeIntervalSince1970: 1_800_000_000)
        let recordedAt = endedAt.addingTimeInterval(300)
        let dueAt = endedAt.addingTimeInterval(86400)
        let completedAt = dueAt.addingTimeInterval(600)

        let successfulDebrief = DebriefRecord(
            schemaVersion: "0.4",
            recordStatus: "immediate_complete",
            participantID: "participant_founder_bridge_001",
            runID: "bridge-success-run",
            bindingID: "valparaiso_central",
            missionID: "m01",
            condition: "A",
            participantRole: "founder",
            startedAtLocal: endedAt.addingTimeInterval(-1800),
            endedAtLocal: endedAt,
            recordedAtLocal: recordedAt,
            recordingDelaySeconds: 300,
            precommittedNextWorkoutAtLocal: dueAt,
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            track: TrackSummary(
                fileName: "bridge-success-run.gpx",
                fileSHA256: String(repeating: "c", count: 64),
                sampleCount: 50,
                startedAt: endedAt.addingTimeInterval(-1800),
                endedAt: endedAt,
                durationSeconds: 1800,
                distanceMeters: 2500,
                meanHorizontalAccuracyMeters: 5,
                maximumSampleGapSeconds: 10
            ),
            routeTraversalEvidence: nil,
            safety: SafetyEvidence(
                routeManuallyChecked: true,
                abort: false,
                abortReason: "",
                neededScreenWhileMoving: false,
                navConflicts: []
            ),
            runtime: RuntimeEvidence(
                completed: true,
                geoSlotsReached: ["slot1"],
                geoFallbacksUsed: [],
                missedOrLateCues: [],
                operatorImprovisationUsed: false,
                audioIncidents: [],
                additionalAudioNotes: "",
                offRouteIncidents: [],
                pauseCount: 0,
                locationIncidents: []
            ),
            immediateDebriefBeforeEdits: ImmediateDebriefEvidence(
                missionGoalInOneSentence: "Goal sentence.",
                momentCompanionBecameImportant: "Companion moment.",
                unaidedMemorableScene: "Memorable scene.",
                attentionDropMoment: "None.",
                whatPhysicalMovementChanged: "Pace change.",
                desireForM02_1To7: 6,
                placeNecessity1To7: 7,
                predictedNextTwist: "Plot twist.",
                nextWorkoutStillScheduled: true
            ),
            recallAfter24h: RecallAfter24HoursEvidence(pending: true, instructions: "Recall in 24h"),
            confounds: ConfoundEvidence(
                unfamiliarCityNovelty: "",
                fatigue: "",
                noise: "",
                weather: "",
                routeQuality: "",
                audioQuality: "",
                elevationOrStairs: ""
            ),
            device: DeviceEvidence(
                model: "iPhone 16 Pro",
                systemName: "iOS",
                systemVersion: "18.5",
                headphones: "AirPods Pro",
                lockScreenUsed: true,
                lockScreenAnswerRecorded: true
            ),
            evidenceLimits: ["Bridge test"]
        )

        let successfulRecall = RecallCompletionRecord(
            schemaVersion: "0.3",
            recordStatus: "recall_24h_complete",
            participantID: "participant_founder_bridge_001",
            runID: "bridge-success-run",
            bindingID: "valparaiso_central",
            missionID: "m01",
            condition: "A",
            audioSHA256: String(repeating: "a", count: 64),
            routeWorkoutFingerprint: String(repeating: "b", count: 64),
            runEndedAtLocal: endedAt,
            dueAtLocal: dueAt,
            completedAtLocal: completedAt,
            unaidedStoryRecall: "I remember Lea and the plaza.",
            unaidedPlaceRecall: ["Plaza Sotomayor", "Muelle Prat"],
            desireForM02_1To7: 6,
            evidenceLimits: ["Recall completed in bridge test."]
        )

        let immURL = tempDir.appendingPathComponent("immediate-success.json")
        let recURL = tempDir.appendingPathComponent("recall-success.json")
        try JSONEncoder.evidence.encode(successfulDebrief).write(to: immURL)
        try JSONEncoder.evidence.encode(successfulRecall).write(to: recURL)

        let pairResult = try runValidator(args: ["--immediate", immURL.path, "--recall", recURL.path])
        XCTAssertEqual(pairResult.exitCode, 0, "Python validator failed on successful pair: \(pairResult.stderr)")
        XCTAssertTrue(pairResult.stdout.contains("[PASS]"), "Validator output should contain [PASS]: \(pairResult.stdout)")

        // 2. Aborted completed immediate debrief validation
        let abortedEndedAt = Date(timeIntervalSince1970: 1_800_000_000)
        let abortedRecordedAt = abortedEndedAt.addingTimeInterval(200)

        let abortedDebrief = DebriefRecord(
            schemaVersion: "0.4",
            recordStatus: "immediate_complete",
            participantID: "participant_founder_bridge_002",
            runID: "bridge-aborted-run",
            bindingID: "valparaiso_central",
            missionID: "m01",
            condition: "A",
            participantRole: "founder",
            startedAtLocal: abortedEndedAt.addingTimeInterval(-300),
            endedAtLocal: abortedEndedAt,
            recordedAtLocal: abortedRecordedAt,
            recordingDelaySeconds: 200,
            precommittedNextWorkoutAtLocal: abortedEndedAt.addingTimeInterval(86400),
            audioSHA256: String(repeating: "d", count: 64),
            routeWorkoutFingerprint: String(repeating: "e", count: 64),
            track: nil,
            routeTraversalEvidence: nil,
            safety: SafetyEvidence(
                routeManuallyChecked: true,
                abort: true,
                abortReason: "Aborted run due to heavy rain and safety hazard",
                neededScreenWhileMoving: false,
                navConflicts: []
            ),
            runtime: RuntimeEvidence(
                completed: false,
                geoSlotsReached: [],
                geoFallbacksUsed: [],
                missedOrLateCues: [],
                operatorImprovisationUsed: false,
                audioIncidents: [],
                additionalAudioNotes: "",
                offRouteIncidents: [],
                pauseCount: 0,
                locationIncidents: []
            ),
            immediateDebriefBeforeEdits: ImmediateDebriefEvidence(
                missionGoalInOneSentence: "Goal sentence.",
                momentCompanionBecameImportant: "Companion moment.",
                unaidedMemorableScene: "Memorable scene.",
                attentionDropMoment: "None.",
                whatPhysicalMovementChanged: "Pace change.",
                desireForM02_1To7: 4,
                placeNecessity1To7: 4,
                predictedNextTwist: "Plot twist.",
                nextWorkoutStillScheduled: false
            ),
            recallAfter24h: RecallAfter24HoursEvidence(pending: false, instructions: ""),
            confounds: ConfoundEvidence(
                unfamiliarCityNovelty: "",
                fatigue: "",
                noise: "",
                weather: "Heavy rain",
                routeQuality: "",
                audioQuality: "",
                elevationOrStairs: ""
            ),
            device: DeviceEvidence(
                model: "iPhone 16 Pro",
                systemName: "iOS",
                systemVersion: "18.5",
                headphones: "AirPods Pro",
                lockScreenUsed: true,
                lockScreenAnswerRecorded: true
            ),
            evidenceLimits: ["Bridge test aborted debrief"]
        )

        let abortedURL = tempDir.appendingPathComponent("immediate-aborted.json")
        try JSONEncoder.evidence.encode(abortedDebrief).write(to: abortedURL)

        let abortedResult = try runValidator(args: [abortedURL.path])
        XCTAssertEqual(abortedResult.exitCode, 0, "Python validator failed on aborted debrief: \(abortedResult.stderr)")
        XCTAssertTrue(abortedResult.stdout.contains("[PASS]"), "Validator output should contain [PASS]: \(abortedResult.stdout)")
    }
}
