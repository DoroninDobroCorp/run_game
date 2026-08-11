import Foundation

enum GPXDocument {
    static func data(samples: [TrackSample], name: String = "Run Game Founder Track") throws -> Data {
        let ordered = samples.sorted { $0.timestamp < $1.timestamp }
        guard !ordered.isEmpty else { throw FounderAppError.noRecordedTrack }
        guard ordered.allSatisfy(\.isValid) else {
            throw FounderAppError.invalidTrack("координаты, высота или accuracy вне допустимого диапазона")
        }
        guard zip(ordered, ordered.dropFirst()).allSatisfy({
            $0.1.timestamp > $0.0.timestamp
        }) else {
            throw FounderAppError.invalidTrack("GPS timestamps должны строго возрастать")
        }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let locale = Locale(identifier: "en_US_POSIX")
        let points = ordered.map { sample in
            let latitude = String(format: "%.7f", locale: locale, sample.latitude)
            let longitude = String(format: "%.7f", locale: locale, sample.longitude)
            let elevation = String(format: "%.2f", locale: locale, sample.elevation)
            let accuracy = String(format: "%.1f", locale: locale, sample.horizontalAccuracy)
            return """
                  <trkpt lat="\(latitude)" lon="\(longitude)">
                    <ele>\(elevation)</ele>
                    <time>\(formatter.string(from: sample.timestamp))</time>
                    <extensions><rg:horizontalAccuracy>\(accuracy)</rg:horizontalAccuracy></extensions>
                  </trkpt>
            """
        }.joined(separator: "\n")

        let xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" creator="Run Game Founder" xmlns="http://www.topografix.com/GPX/1/1" xmlns:rg="urn:run-game:gpx:founder:0.2">
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
        let suffix = UUID().uuidString.prefix(8).lowercased()
        let url = directory.appendingPathComponent("\(sanitized(prefix))-\(fileTimestamp())-\(suffix).gpx")
        try FileDurability.writeFinalEvidence(data: data(samples: samples), to: url)
        return url
    }

    static func parseSamples(from data: Data) throws -> [TrackSample] {
        let parser = XMLParser(data: data)
        let delegate = GPXParserDelegate()
        parser.delegate = delegate
        guard parser.parse() else {
            throw FounderAppError.invalidTrack("XMLParser failed to parse GPX data: \(parser.parserError?.localizedDescription ?? "unknown error")")
        }
        return delegate.samples
    }

    private static func fileTimestamp() -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter.string(from: Date())
    }

    static func sanitized(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let scalars = value.unicodeScalars.map { allowed.contains($0) ? Character(String($0)) : "-" }
        let result = String(scalars).replacingOccurrences(of: "--", with: "-")
        return result.trimmingCharacters(in: CharacterSet(charactersIn: "-"))
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

private final class GPXParserDelegate: NSObject, XMLParserDelegate {
    private(set) var samples: [TrackSample] = []
    private var currentElement = ""
    private var currentLat: Double?
    private var currentLon: Double?
    private var currentEle: Double?
    private var currentTime: Date?
    private var currentAcc: Double?
    private var currentText = ""

    nonisolated(unsafe) private static let isoFormatterFractional: ISO8601DateFormatter = {
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fmt
    }()

    nonisolated(unsafe) private static let isoFormatterStandard: ISO8601DateFormatter = {
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime]
        return fmt
    }()

    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String : String] = [:]) {
        currentElement = elementName
        currentText = ""
        if elementName == "trkpt" {
            currentLat = Double(attributeDict["lat"] ?? "")
            currentLon = Double(attributeDict["lon"] ?? "")
            currentEle = nil
            currentTime = nil
            currentAcc = nil
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        currentText += string
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
        let trimmed = currentText.trimmingCharacters(in: .whitespacesAndNewlines)
        if elementName == "ele" {
            currentEle = Double(trimmed)
        } else if elementName == "time" {
            currentTime = Self.isoFormatterFractional.date(from: trimmed) ?? Self.isoFormatterStandard.date(from: trimmed)
        } else if elementName == "rg:horizontalAccuracy" || elementName == "horizontalAccuracy" {
            currentAcc = Double(trimmed)
        } else if elementName == "trkpt" {
            if let lat = currentLat, let lon = currentLon, let ele = currentEle, let time = currentTime {
                let acc = currentAcc ?? 5.0
                let sample = TrackSample(
                    latitude: lat,
                    longitude: lon,
                    elevation: ele,
                    horizontalAccuracy: acc,
                    timestamp: time
                )
                if sample.isValid {
                    samples.append(sample)
                }
            }
        }
        currentText = ""
    }
}
