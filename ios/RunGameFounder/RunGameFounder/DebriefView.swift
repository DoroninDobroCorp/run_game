import SwiftUI
import UIKit

struct DebriefView: View {
    private enum LockScreenAnswer: String, CaseIterable, Identifiable {
        case unanswered = "Не выбрано"
        case yes = "Да"
        case no = "Нет"

        var id: String { rawValue }
    }

    @EnvironmentObject private var appModel: AppModel
    let mission: MissionConfig
    let context: RunSessionContext

    @State private var missionGoal = ""
    @State private var companionMoment = ""
    @State private var memorableScene = ""
    @State private var attentionDrop = ""
    @State private var movementEffect = ""
    @State private var predictedTwist = ""
    @State private var desireForM02 = 4.0
    @State private var placeNecessity = 4.0
    @State private var nextWorkoutStillScheduled = true

    @State private var abortReason: String
    @State private var neededScreenWhileMoving = false
    @State private var navConflicts = ""
    @State private var geoSlotsReached = ""
    @State private var geoFallbacksUsed = ""
    @State private var missedOrLateCues = ""
    @State private var operatorImprovisationUsed = false
    @State private var additionalAudioNotes = ""
    @State private var offRouteIncidents = ""

    @State private var unfamiliarCityNovelty = ""
    @State private var fatigue = ""
    @State private var noise = ""
    @State private var weather = ""
    @State private var routeQuality = ""
    @State private var audioQuality = ""
    @State private var elevationOrStairs = ""

    @State private var deviceModel = ""
    @State private var headphones = ""
    @State private var lockScreenAnswer: LockScreenAnswer = .unanswered
    @State private var exportedURL: URL?
    @State private var errorMessage: String?

    init(mission: MissionConfig, context: RunSessionContext) {
        self.mission = mission
        self.context = context
        let draft = Self.loadRecord(
            missionID: context.missionID,
            runID: context.runID,
            suffix: "draft",
            expectedStatus: "draft_incomplete",
            context: context
        )
        _missionGoal = State(initialValue: draft?.immediateDebriefBeforeEdits.missionGoalInOneSentence ?? "")
        _companionMoment = State(initialValue: draft?.immediateDebriefBeforeEdits.momentCompanionBecameImportant ?? "")
        _memorableScene = State(initialValue: draft?.immediateDebriefBeforeEdits.unaidedMemorableScene ?? "")
        _attentionDrop = State(initialValue: draft?.immediateDebriefBeforeEdits.attentionDropMoment ?? "")
        _movementEffect = State(initialValue: draft?.immediateDebriefBeforeEdits.whatPhysicalMovementChanged ?? "")
        _predictedTwist = State(initialValue: draft?.immediateDebriefBeforeEdits.predictedNextTwist ?? "")
        _desireForM02 = State(initialValue: Double(draft?.immediateDebriefBeforeEdits.desireForM02_1To7 ?? 4))
        _placeNecessity = State(initialValue: Double(draft?.immediateDebriefBeforeEdits.placeNecessity1To7 ?? 4))
        _nextWorkoutStillScheduled = State(initialValue: draft?.immediateDebriefBeforeEdits.nextWorkoutStillScheduled ?? true)
        _abortReason = State(initialValue: draft?.safety.abortReason ?? context.abortReason)
        _neededScreenWhileMoving = State(initialValue: draft?.safety.neededScreenWhileMoving ?? false)
        _navConflicts = State(initialValue: draft?.safety.navConflicts.joined(separator: "\n") ?? "")
        _geoSlotsReached = State(initialValue: draft?.runtime.geoSlotsReached.joined(separator: "\n") ?? "")
        _geoFallbacksUsed = State(initialValue: draft?.runtime.geoFallbacksUsed.joined(separator: "\n") ?? "")
        _missedOrLateCues = State(initialValue: draft?.runtime.missedOrLateCues.joined(separator: "\n") ?? "")
        _operatorImprovisationUsed = State(initialValue: draft?.runtime.operatorImprovisationUsed ?? false)
        _additionalAudioNotes = State(initialValue: draft?.runtime.additionalAudioNotes ?? "")
        _offRouteIncidents = State(initialValue: draft?.runtime.offRouteIncidents.joined(separator: "\n") ?? "")
        _unfamiliarCityNovelty = State(initialValue: draft?.confounds.unfamiliarCityNovelty ?? "")
        _fatigue = State(initialValue: draft?.confounds.fatigue ?? "")
        _noise = State(initialValue: draft?.confounds.noise ?? "")
        _weather = State(initialValue: draft?.confounds.weather ?? "")
        _routeQuality = State(initialValue: draft?.confounds.routeQuality ?? "")
        _audioQuality = State(initialValue: draft?.confounds.audioQuality ?? "")
        _elevationOrStairs = State(initialValue: draft?.confounds.elevationOrStairs ?? "")
        _deviceModel = State(initialValue: draft?.device.model ?? "")
        _headphones = State(initialValue: draft?.device.headphones ?? "")
        if let device = draft?.device, device.lockScreenAnswerRecorded {
            _lockScreenAnswer = State(initialValue: device.lockScreenUsed ? .yes : .no)
        } else {
            _lockScreenAnswer = State(initialValue: .unanswered)
        }
    }

    var body: some View {
        Form {
            Section("Сразу, до обсуждения и правок") {
                prompt("Цель миссии одним предложением *", text: $missionGoal)
                prompt("Когда Леа стала важна как напарник? *", text: $companionMoment)
                prompt("Какая сцена запомнилась без подсказки? *", text: $memorableScene)
                prompt("Где внимание просело? Напиши «не было», если нигде. *", text: $attentionDrop)
                prompt("Что физическое движение изменило в истории? *", text: $movementEffect)
                prompt("Какой следующий поворот ты ожидаешь? *", text: $predictedTwist)
            }

            Section("Safety и runtime") {
                if context.aborted {
                    prompt("Почему тест был остановлен? *", text: $abortReason)
                }
                Toggle("Пришлось смотреть на экран в движении", isOn: $neededScreenWhileMoving)
                prompt("Конфликты NAV/дороги/истории", text: $navConflicts)
                prompt("Какие geo-slots фактически достигнуты", text: $geoSlotsReached)
                prompt("Какие fallback использованы", text: $geoFallbacksUsed)
                prompt("Пропущенные или поздние cue", text: $missedOrLateCues)
                Toggle("Была операторская импровизация", isOn: $operatorImprovisationUsed)
                prompt("Дополнительные аудио-инциденты", text: $additionalAudioNotes)
                prompt("Off-route события", text: $offRouteIncidents)

                if !context.audioIncidents.isEmpty || !context.locationIncidents.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Автоматически зафиксировано").font(.subheadline.bold())
                        ForEach(context.audioIncidents + context.locationIncidents, id: \.self) {
                            Text("• \($0)").font(.caption)
                        }
                    }
                }
            }

            Section("Оценки") {
                score("Хочу пройти M2", value: $desireForM02)
                score("История нуждалась именно в этих местах", value: $placeNecessity)
                Toggle("Следующая тренировка всё ещё запланирована", isOn: $nextWorkoutStillScheduled)
                Text("Precommit: \(context.precommittedNextWorkoutAt.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Контекст и confounds") {
                prompt("Новизна незнакомого города", text: $unfamiliarCityNovelty)
                prompt("Усталость", text: $fatigue)
                prompt("Шум", text: $noise)
                prompt("Погода", text: $weather)
                prompt("Качество маршрута", text: $routeQuality)
                prompt("Качество аудио", text: $audioQuality)
                prompt("Рельеф или лестницы", text: $elevationOrStairs)
            }

            Section("Устройство") {
                TextField("Модель iPhone *", text: $deviceModel)
                TextField("Наушники *", text: $headphones)
                Picker("Экран был заблокирован? *", selection: $lockScreenAnswer) {
                    ForEach(LockScreenAnswer.allCases) { answer in
                        Text(answer.rawValue).tag(answer)
                    }
                }
                Text("\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)")
                    .foregroundStyle(.secondary)
            }

            Section("Evidence package") {
                LabeledContent("Run ID", value: context.runID)
                LabeledContent("Audio", value: String(context.audioSHA256.prefix(12)) + "…")
                if let track = context.track {
                    LabeledContent("GPX", value: track.fileName)
                    LabeledContent(
                        "GPS",
                        value: "\(track.sampleCount) точек · \(String(format: "%.2f", track.distanceMeters / 1000)) км"
                    )
                    LabeledContent("GPX SHA", value: String(track.fileSHA256.prefix(12)) + "…")
                    if let traversal = context.routeTraversalEvidence {
                        LabeledContent(
                            "Ordered route",
                            value: "\(traversal.reachedRoutePointIDs.count)/\(mission.routePoints.count) · closure \(Int(traversal.startFinishClosureMeters)) м"
                        )
                    }
                    if let trackURL {
                        ShareLink(item: trackURL) {
                            Label("Экспортировать GPX", systemImage: "square.and.arrow.up")
                        }
                    } else {
                        Text("GPX отсутствует или его SHA изменился; файл не экспортируется как валидное evidence.")
                            .font(.caption)
                            .foregroundStyle(RunGameTheme.warning)
                    }
                } else {
                    Text("GPX отсутствует: результат не может считаться completed.")
                        .foregroundStyle(RunGameTheme.warning)
                }

                VStack(alignment: .leading, spacing: 6) {
                    Label("Blind Export Guidance", systemImage: "eye.slash.fill")
                        .font(.subheadline.bold())
                    Text("Для сохранения объективности заполняйте текстовые поля без подглядывания в ранее записанный immediate JSON или аудиоматериалы.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Button("Сохранить immediate JSON", action: saveFinal)
                    .accessibilityIdentifier("saveDebriefButton")
                    .disabled(!canSaveFinal)
                if !canSaveFinal {
                    Text(saveRequirementMessage)
                        .font(.caption)
                        .foregroundStyle(RunGameTheme.warning)
                }
                if let exportedURL {
                    ShareLink(item: exportedURL) {
                        Label("Экспортировать evidence JSON", systemImage: "square.and.arrow.up")
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(RunGameTheme.warning)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Дебриф M1")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear(perform: recoverCompletedRecordIfPresent)
        .onDisappear {
            if exportedURL == nil { saveDraft() }
        }
    }

    private var canSaveFinal: Bool {
        let required = [missionGoal, companionMoment, memorableScene, attentionDrop, movementEffect, predictedTwist, deviceModel, headphones]
        return required.allSatisfy { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            && lockScreenAnswer != .unanswered
            && (!context.aborted || !abortReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            && (!context.completed || trackURL != nil)
            && (!context.completed || context.routeTraversalEvidence?.isSufficient(for: mission) == true)
            && exportedURL == nil
    }

    private var saveRequirementMessage: String {
        if context.completed && trackURL == nil {
            return "Completed evidence требует локальный GPX с неизменным SHA-256."
        }
        if context.completed && context.routeTraversalEvidence?.isSufficient(for: mission) != true {
            return "Completed evidence требует ordered start→POI→finish traversal у public start."
        }
        return context.completed
            ? "Заполни обязательные поля (*), модель/наушники и ответ о lock screen."
            : "Заполни обязательные поля (*), модель/наушники, ответ о lock screen и причину остановки."
    }

    private func prompt(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold))
            TextEditor(text: text)
                .frame(minHeight: 72)
        }
    }

    private func score(_ title: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                Spacer()
                Text("\(Int(value.wrappedValue))/7").monospacedDigit().foregroundStyle(RunGameTheme.electric)
            }
            Slider(value: value, in: 1...7, step: 1)
        }
    }

    private func makeRecord(status: String) -> DebriefRecord {
        let recordedAt = Date()
        let delay = recordedAt.timeIntervalSince(context.endedAt)
        return DebriefRecord(
            schemaVersion: "0.3",
            recordStatus: status,
            runID: context.runID,
            bindingID: context.bindingID,
            missionID: context.missionID,
            condition: context.condition,
            participantRole: "founder",
            startedAtLocal: context.startedAt,
            endedAtLocal: context.endedAt,
            recordedAtLocal: recordedAt,
            recordingDelaySeconds: delay,
            precommittedNextWorkoutAtLocal: context.precommittedNextWorkoutAt,
            audioSHA256: context.audioSHA256,
            routeWorkoutFingerprint: context.routeWorkoutFingerprint,
            track: context.track,
            routeTraversalEvidence: context.routeTraversalEvidence,
            safety: SafetyEvidence(
                routeManuallyChecked: true,
                abort: context.aborted,
                abortReason: abortReason,
                neededScreenWhileMoving: neededScreenWhileMoving,
                navConflicts: list(from: navConflicts)
            ),
            runtime: RuntimeEvidence(
                completed: context.completed
                    && trackURL != nil
                    && context.routeTraversalEvidence?.isSufficient(for: mission) == true,
                geoSlotsReached: list(from: geoSlotsReached),
                geoFallbacksUsed: list(from: geoFallbacksUsed),
                missedOrLateCues: list(from: missedOrLateCues),
                operatorImprovisationUsed: operatorImprovisationUsed,
                audioIncidents: context.audioIncidents,
                additionalAudioNotes: additionalAudioNotes,
                offRouteIncidents: list(from: offRouteIncidents),
                pauseCount: context.pauseCount,
                locationIncidents: context.locationIncidents
            ),
            immediateDebriefBeforeEdits: ImmediateDebriefEvidence(
                missionGoalInOneSentence: missionGoal,
                momentCompanionBecameImportant: companionMoment,
                unaidedMemorableScene: memorableScene,
                attentionDropMoment: attentionDrop,
                whatPhysicalMovementChanged: movementEffect,
                desireForM02_1To7: Int(desireForM02),
                placeNecessity1To7: Int(placeNecessity),
                predictedNextTwist: predictedTwist,
                nextWorkoutStillScheduled: nextWorkoutStillScheduled
            ),
            recallAfter24h: RecallAfter24HoursEvidence(
                pending: true,
                instructions: "Через 24 часа отдельно зафиксировать unaided story/place recall и желание M2, не перечитывая immediate JSON."
            ),
            confounds: ConfoundEvidence(
                unfamiliarCityNovelty: unfamiliarCityNovelty,
                fatigue: fatigue,
                noise: noise,
                weather: weather,
                routeQuality: routeQuality,
                audioQuality: audioQuality,
                elevationOrStairs: elevationOrStairs
            ),
            device: DeviceEvidence(
                model: deviceModel,
                systemName: UIDevice.current.systemName,
                systemVersion: UIDevice.current.systemVersion,
                headphones: headphones,
                lockScreenUsed: lockScreenAnswer == .yes,
                lockScreenAnswerRecorded: lockScreenAnswer != .unanswered
            ),
            evidenceLimits: [
                "Founder knows the graph, so this run cannot validate twist surprise.",
                "One traveler-fixture run does not validate repeated use of a home territory.",
                "A completed immediate record is not the pending 24-hour recall."
            ]
        )
    }

    private func saveFinal() {
        guard canSaveFinal else { return }
        do {
            let url = evidenceURL(suffix: "immediate")
            if FileManager.default.fileExists(atPath: url.path) {
                guard Self.loadRecord(
                    missionID: context.missionID,
                    runID: context.runID,
                    suffix: "immediate",
                    expectedStatus: "immediate_complete",
                    context: context
                ) != nil else {
                    errorMessage = "Существующий immediate JSON не прошёл проверку; файл не перезаписан."
                    return
                }
                FileDurability.markExcludedFromBackup(url: url)
            } else {
                let data = try JSONEncoder.evidence.encode(makeRecord(status: "immediate_complete"))
                try FileDurability.writeFinalEvidence(data: data, to: url)
                guard FileDurability.verifySHA256(of: url, expectedSHA: BundleIntegrity.sha256(of: data)) else {
                    errorMessage = "Записанный immediate JSON не прошёл проверку SHA-256."
                    return
                }
            }
            completeFinalSave(at: url)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func list(from text: String) -> [String] {
        text.split(whereSeparator: { $0.isNewline || $0 == ";" })
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func saveDraft() {
        guard Self.loadRecord(
            missionID: context.missionID,
            runID: context.runID,
            suffix: "immediate",
            expectedStatus: "immediate_complete",
            context: context
        ) == nil else { return }
        do {
            let url = evidenceURL(suffix: "draft")
            let data = try JSONEncoder.evidence.encode(makeRecord(status: "draft_incomplete"))
            try FileDurability.writeAtomicDraft(data: data, to: url)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func evidenceURL(suffix: String) -> URL {
        Self.evidenceURL(missionID: context.missionID, runID: context.runID, suffix: suffix)
    }

    private func recoverCompletedRecordIfPresent() {
        guard exportedURL == nil,
              Self.loadRecord(
                missionID: context.missionID,
                runID: context.runID,
                suffix: "immediate",
                expectedStatus: "immediate_complete",
                context: context
              ) != nil else { return }
        completeFinalSave(at: evidenceURL(suffix: "immediate"))
    }

    private func completeFinalSave(at url: URL) {
        let draft = evidenceURL(suffix: "draft")
        if FileManager.default.fileExists(atPath: draft.path) {
            try? FileManager.default.removeItem(at: draft)
        }
        if context.completed && !context.aborted {
            appModel.scheduleRecall(for: context)
        }
        appModel.completeDebrief(runID: context.runID)
        appModel.refreshRecoveredTracks()
        exportedURL = url
        errorMessage = nil
    }

    private static func evidenceURL(missionID: String, runID: String, suffix: String) -> URL {
        let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return directory.appendingPathComponent("\(missionID)-\(runID)-\(suffix).json")
    }

    private var trackURL: URL? {
        guard let fileName = context.track?.fileName,
              !fileName.isEmpty,
              URL(fileURLWithPath: fileName).lastPathComponent == fileName,
              !fileName.contains("/"),
              !fileName.contains("\\") else { return nil }
        let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let url = directory.appendingPathComponent(fileName)
        guard FileManager.default.fileExists(atPath: url.path),
              let expectedSHA = context.track?.fileSHA256,
              FileDurability.verifySHA256(of: url, expectedSHA: expectedSHA) else {
            return nil
        }
        FileDurability.markExcludedFromBackup(url: url)
        return url
    }

    private static func loadRecord(
        missionID: String,
        runID: String,
        suffix: String,
        expectedStatus: String,
        context: RunSessionContext
    ) -> DebriefRecord? {
        let url = evidenceURL(missionID: missionID, runID: runID, suffix: suffix)
        guard let data = try? Data(contentsOf: url),
              let record = try? JSONDecoder.evidence.decode(DebriefRecord.self, from: data),
              record.schemaVersion == "0.3" || record.schemaVersion == "0.2",
              record.recordStatus == expectedStatus,
              record.runID == context.runID,
              record.missionID == context.missionID,
              record.bindingID == context.bindingID,
              record.audioSHA256.caseInsensitiveCompare(context.audioSHA256) == .orderedSame,
              record.routeWorkoutFingerprint == context.routeWorkoutFingerprint else { return nil }
        return record
    }
}

struct RecallView: View {
    @EnvironmentObject private var appModel: AppModel
    let record: PendingRecall

    @State private var storyRecall = ""
    @State private var placeRecall = ""
    @State private var desireForM02 = 4.0
    @State private var exportedURL: URL?
    @State private var errorMessage: String?
    @State private var now = Date()

    init(record: PendingRecall) {
        self.record = record
        let draft = Self.loadRecord(
            record: record,
            suffix: "recall-24h-draft",
            expectedStatus: "recall_24h_draft"
        )
        _storyRecall = State(initialValue: draft?.unaidedStoryRecall ?? "")
        _placeRecall = State(initialValue: draft?.unaidedPlaceRecall.joined(separator: "\n") ?? "")
        _desireForM02 = State(initialValue: Double(draft?.desireForM02_1To7 ?? 4))
    }

    var body: some View {
        Form {
            Section("Без подсказок и перечитывания immediate JSON") {
                recallPrompt("Что ты помнишь об истории? *", text: $storyRecall)
                recallPrompt("Какие места вспоминаются? По одному на строку. *", text: $placeRecall)
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Хочу пройти M2")
                        Spacer()
                        Text("\(Int(desireForM02))/7").monospacedDigit()
                    }
                    Slider(value: $desireForM02, in: 1...7, step: 1)
                }
            }
            .disabled(!isDue)

            Section("Окно recall") {
                LabeledContent("Run ID", value: record.runID)
                LabeledContent("Забег завершён", value: record.runEndedAt.formatted(date: .abbreviated, time: .shortened))
                LabeledContent("Не раньше", value: record.dueAt.formatted(date: .abbreviated, time: .shortened))
                if !isDue {
                    Text("Recall пока заблокирован, чтобы сохранить честное 24-часовое окно.")
                        .foregroundStyle(RunGameTheme.warning)
                }
            }

            Section("Локальный evidence") {
                Button("Сохранить 24h recall JSON", action: save)
                    .accessibilityIdentifier("saveRecallButton")
                    .disabled(!canSave)
                if let exportedURL {
                    ShareLink(item: exportedURL) {
                        Label("Экспортировать recall JSON", systemImage: "square.and.arrow.up")
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(RunGameTheme.warning)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(RunGameTheme.ink.ignoresSafeArea())
        .navigationTitle("Recall через 24 часа")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear(perform: recoverCompletedRecordIfPresent)
        .onDisappear {
            if exportedURL == nil { saveDraft() }
        }
        .task(id: record.dueAt) {
            now = Date()
            let delay = record.dueAt.timeIntervalSince(now)
            if delay > 0 {
                try? await Task.sleep(for: .seconds(delay))
                now = Date()
            }
        }
    }

    private var places: [String] {
        placeRecall
            .split(whereSeparator: { $0.isNewline || $0 == ";" })
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private var canSave: Bool {
        isDue
            && !storyRecall.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !places.isEmpty
            && exportedURL == nil
    }

    private var isDue: Bool { now >= record.dueAt }

    private func recallPrompt(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold))
            TextEditor(text: text).frame(minHeight: 100)
        }
    }

    private func save() {
        guard canSave else { return }
        let completion = makeRecord(status: "recall_24h_complete")
        do {
            let url = evidenceURL(suffix: "recall-24h")
            if FileManager.default.fileExists(atPath: url.path) {
                guard Self.loadRecord(
                    record: record,
                    suffix: "recall-24h",
                    expectedStatus: "recall_24h_complete"
                ) != nil else {
                    errorMessage = "Существующий 24h recall не прошёл проверку; файл не перезаписан."
                    return
                }
                FileDurability.markExcludedFromBackup(url: url)
            } else {
                let data = try JSONEncoder.evidence.encode(completion)
                try FileDurability.writeFinalEvidence(data: data, to: url)
                guard FileDurability.verifySHA256(of: url, expectedSHA: BundleIntegrity.sha256(of: data)) else {
                    errorMessage = "Записанный 24h recall не прошёл проверку SHA-256."
                    return
                }
            }
            completeFinalSave(at: url)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func makeRecord(status: String) -> RecallCompletionRecord {
        RecallCompletionRecord(
            schemaVersion: "0.2",
            recordStatus: status,
            runID: record.runID,
            bindingID: record.bindingID,
            missionID: record.missionID,
            condition: record.condition,
            audioSHA256: record.audioSHA256,
            routeWorkoutFingerprint: record.routeWorkoutFingerprint,
            runEndedAtLocal: record.runEndedAt,
            dueAtLocal: record.dueAt,
            completedAtLocal: Date(),
            unaidedStoryRecall: storyRecall.trimmingCharacters(in: .whitespacesAndNewlines),
            unaidedPlaceRecall: places,
            desireForM02_1To7: Int(desireForM02),
            evidenceLimits: [
                "Recall was entered by the founder without an in-app view of the immediate record.",
                "This separate file must be paired by run_id; it does not rewrite immediate evidence."
            ]
        )
    }

    private func saveDraft() {
        guard isDue,
              !storyRecall.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !places.isEmpty,
              Self.loadRecord(
                record: record,
                suffix: "recall-24h",
                expectedStatus: "recall_24h_complete"
              ) == nil else { return }
        do {
            let data = try JSONEncoder.evidence.encode(makeRecord(status: "recall_24h_draft"))
            try FileDurability.writeAtomicDraft(data: data, to: evidenceURL(suffix: "recall-24h-draft"))
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func recoverCompletedRecordIfPresent() {
        now = Date()
        guard exportedURL == nil,
              Self.loadRecord(
                record: record,
                suffix: "recall-24h",
                expectedStatus: "recall_24h_complete"
              ) != nil else { return }
        completeFinalSave(at: evidenceURL(suffix: "recall-24h"))
    }

    private func completeFinalSave(at url: URL) {
        let draft = evidenceURL(suffix: "recall-24h-draft")
        if FileManager.default.fileExists(atPath: draft.path) {
            try? FileManager.default.removeItem(at: draft)
        }
        exportedURL = url
        errorMessage = nil
        appModel.completeRecall(runID: record.runID)
        appModel.refreshRecoveredTracks()
    }

    private func evidenceURL(suffix: String) -> URL {
        Self.evidenceURL(record: record, suffix: suffix)
    }

    private static func evidenceURL(record: PendingRecall, suffix: String) -> URL {
        let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return directory.appendingPathComponent("\(record.missionID)-\(record.runID)-\(suffix).json")
    }

    private static func loadRecord(
        record: PendingRecall,
        suffix: String,
        expectedStatus: String
    ) -> RecallCompletionRecord? {
        let url = evidenceURL(record: record, suffix: suffix)
        guard let data = try? Data(contentsOf: url),
              let completion = try? JSONDecoder.evidence.decode(RecallCompletionRecord.self, from: data),
              completion.schemaVersion == "0.2",
              completion.recordStatus == expectedStatus,
              completion.runID == record.runID,
              completion.missionID == record.missionID,
              completion.bindingID == record.bindingID,
              completion.condition == record.condition,
              completion.audioSHA256.caseInsensitiveCompare(record.audioSHA256) == .orderedSame,
              completion.routeWorkoutFingerprint == record.routeWorkoutFingerprint,
              abs(completion.runEndedAtLocal.timeIntervalSince(record.runEndedAt)) < 1,
              abs(completion.dueAtLocal.timeIntervalSince(record.dueAt)) < 1 else { return nil }
        if expectedStatus == "recall_24h_complete" {
            guard completion.completedAtLocal >= completion.dueAtLocal,
                  !completion.unaidedStoryRecall.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  !completion.unaidedPlaceRecall.isEmpty,
                  (1...7).contains(completion.desireForM02_1To7) else { return nil }
        }
        return completion
    }
}

private extension JSONEncoder {
    static var evidence: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}

private extension JSONDecoder {
    static var evidence: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}
