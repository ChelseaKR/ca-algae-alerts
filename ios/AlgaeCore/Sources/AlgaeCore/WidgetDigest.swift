import Foundation

/// The small file the app writes for the widget, so the widget never
/// decodes the full snapshot and never makes a network request.
public struct WidgetDigest: Codable, Equatable, Sendable {
    public struct Row: Codable, Equatable, Sendable {
        public let id: Waterbody.ID
        public let name: String
        public let line: String
        public let isAdvisory: Bool

        /// `line` for VoiceOver, without the spoken " · ".
        public var spokenLine: String { line.replacingOccurrences(of: " · ", with: ", ") }
    }

    /// Before the purchase: no favorites, only the data's date and count.
    public let locked: Bool
    public let fileDate: PlainDate?
    public let advisoryCount: Int
    public let rows: [Row]
    /// Favorites the snapshot no longer has. Counted, never shown as clear.
    public let missingFavorites: Int
    public let lastCheckFailed: Bool

    public static let empty = WidgetDigest(locked: true, fileDate: nil, advisoryCount: 0, rows: [], missingFavorites: 0, lastCheckFailed: false)

    public static func build(snapshot: Snapshot?, favorites: Favorites, isEntitled: Bool, lastCheckFailed: Bool) -> WidgetDigest {
        guard let snapshot else { return .empty }
        let advisoryCount = snapshot.waterbodies.filter { $0.status.kind == .advisory }.count
        guard FreeTier.widgetUnlocked(isEntitled: isEntitled) else {
            return WidgetDigest(locked: true, fileDate: snapshot.sourceFile.fileDate, advisoryCount: advisoryCount, rows: [], missingFavorites: 0, lastCheckFailed: lastCheckFailed)
        }
        var rows: [Row] = []
        var missing = 0
        for id in favorites.ids {
            guard let water = snapshot.waterbody(id: id) else { missing += 1; continue }
            rows.append(Row(id: water.id, name: water.name, line: StatusWording.shortLine(water.status), isAdvisory: water.status.kind == .advisory))
        }
        return WidgetDigest(locked: false, fileDate: snapshot.sourceFile.fileDate, advisoryCount: advisoryCount, rows: rows, missingFavorites: missing, lastCheckFailed: lastCheckFailed)
    }
}
