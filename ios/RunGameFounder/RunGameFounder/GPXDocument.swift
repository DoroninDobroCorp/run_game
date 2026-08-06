import Foundation

enum GPXDocument {
    static func data(samples: [TrackSample], name: String = "Run Game Founder Track") throws -> Data {
        guard !samples.isEmpty else { throw FounderAppError.noRecordedTrack }
        let formatter = ISO8601DateFormatter()
        let points = samples.map { sample in
            let latitude = String(format: "%.7f", sample.latitude)
            let longitude = String(format: "%.7f", sample.longitude)
            let elevation = String(format: "%.2f", sample.elevation)
            return """
                  <trkpt lat="\(latitude)" lon="\(longitude)">
                    <ele>\(elevation)</ele>
                    <time>\(formatter.string(from: sample.timestamp))</time>
                    <extensions><horizontalAccuracy>\(String(format: "%.1f", sample.horizontalAccuracy))</horizontalAccuracy></extensions>
                  </trkpt>
            """
        }.joined(separator: "\n")

        let xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" creator="Run Game Founder" xmlns="http://www.topografix.com/GPX/1/1">
          <trk>
            <name>\(escape(name))</name>
            <trkseg>
        \(points)
            </trkseg>
          </trk>
        </gpx>
        """
        return Data(xml.utf8)
    }

    static func save(samples: [TrackSample], prefix: String) throws -> URL {
        let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let url = directory.appendingPathComponent("\(prefix)-\(fileTimestamp()).gpx")
        try data(samples: samples).write(to: url, options: .atomic)
        return url
    }

    private static func fileTimestamp() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter.string(from: Date())
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
            .replacingOccurrences(of: "'", with: "&apos;")
    }
}
