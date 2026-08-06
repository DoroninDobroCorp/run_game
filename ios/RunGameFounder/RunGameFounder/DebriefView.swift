import SwiftUI

struct DebriefView: View {
    let mission: MissionConfig
    let aborted: Bool
    @State private var missionGoal = ""
    @State private var memorableScene = ""
    @State private var attentionDrop = ""
    @State private var movementEffect = ""
    @State private var desireForM02 = 4.0
    @State private var placeNecessity = 4.0
    @State private var abortReason = ""
    @State private var notes = ""
    @State private var exportedURL: URL?
    @State private var errorMessage: String?

    var body: some View {
        Form {
            Section("Сразу, до обсуждения и правок") {
                prompt("Цель миссии одним предложением", text: $missionGoal)
                prompt("Какая сцена запомнилась без подсказки?", text: $memorableScene)
                prompt("Где внимание просело?", text: $attentionDrop)
                prompt("Что физическое движение изменило в истории?", text: $movementEffect)
            }
            if aborted {
                Section("Остановка") {
                    prompt("Почему тест был остановлен?", text: $abortReason)
                }
            }
            Section("Оценки") {
                score("Хочу пройти M2", value: $desireForM02)
                score("История нуждалась именно в этих местах", value: $placeNecessity)
            }
            Section("Дополнительно") {
                prompt("Шум, погода, маршрут, аудио и другие помехи", text: $notes)
            }
            Section {
                Button("Сохранить локальный JSON", action: save)
                if let exportedURL {
                    ShareLink(item: exportedURL) {
                        Label("Экспортировать дебриф", systemImage: "square.and.arrow.up")
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
    }

    private func prompt(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold))
            TextEditor(text: text)
                .frame(minHeight: 78)
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

    private func save() {
        let record = DebriefRecord(
            schemaVersion: "0.1",
            missionID: mission.missionID,
            bindingID: mission.bindingID,
            completedAt: Date(),
            completed: !aborted,
            aborted: aborted,
            abortReason: abortReason,
            missionGoal: missionGoal,
            memorableScene: memorableScene,
            attentionDrop: attentionDrop,
            movementEffect: movementEffect,
            desireForM02: Int(desireForM02),
            placeNecessity: Int(placeNecessity),
            notes: notes
        )
        do {
            let data = try JSONEncoder.pretty.encode(record)
            let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = directory.appendingPathComponent("m01-founder-debrief.json")
            try data.write(to: url, options: .atomic)
            exportedURL = url
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private extension JSONEncoder {
    static var pretty: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
}
