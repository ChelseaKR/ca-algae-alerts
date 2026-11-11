import Foundation

/// What the app last saw for each favorite, so an alert announces only a
/// change. Saved for everyone, purchased or not, so a later purchase does
/// not announce every advisory that came while alerts were locked.
public struct AlertBaseline: Codable, Equatable, Sendable {
    public struct Seen: Codable, Equatable, Sendable {
        public let kind: Status.Kind
        public let tier: AdvisoryTier?
        public let posted: PlainDate?

        public init(_ status: Status) {
            kind = status.kind
            tier = status.tier
            posted = status.posted
        }
    }

    public var seen: [Waterbody.ID: Seen]
    public init(seen: [Waterbody.ID: Seen] = [:]) { self.seen = seen }
}

public struct PlannedNotification: Equatable, Sendable, Identifiable {
    public let id: String
    public let waterID: Waterbody.ID
    public let title: String
    public let body: String

    public var userInfo: [String: String] { [WaterLink.notificationWaterKey: waterID] }
}

/// The on-device alert rule (docs/DECISIONS.md 0006). A favorite alerts
/// when its latest state record becomes an advisory (from no advisory, an
/// unclassified report, or an end the state recorded), or when an
/// advisory's level changes. A weekly re-posting of the same level is not a
/// new advisory and does not alert. The first time the app sees a favorite,
/// it only records what is there.
///
/// A favorite the snapshot no longer has keeps its baseline, so its return
/// does not announce an advisory the person already knew about.
public enum AlertPlanner {
    public static func plan(
        favorites: Set<Waterbody.ID>,
        snapshot: Snapshot,
        baseline: AlertBaseline
    ) -> (notifications: [PlannedNotification], baseline: AlertBaseline) {
        var next = baseline
        var out: [PlannedNotification] = []
        for water in snapshot.waterbodies where favorites.contains(water.id) {
            // A state whose data is unavailable (DECISIONS 0024): no alert,
            // and the baseline is kept, so its return announces only a real
            // change since the last current read.
            if water.status.unavailable != nil { continue }
            let now = AlertBaseline.Seen(water.status)
            defer { next.seen[water.id] = now }
            guard let before = baseline.seen[water.id], now.kind == .advisory else { continue }
            if before.kind != .advisory {
                out.append(notification(for: water, changed: false))
            } else if before.tier != now.tier {
                out.append(notification(for: water, changed: true))
            }
        }
        return (out.sorted { $0.waterID < $1.waterID }, next)
    }

    static func notification(for water: Waterbody, changed: Bool) -> PlannedNotification {
        let status = water.status
        let level = StatusWording.levelName(status)
        let posted = status.posted?.label ?? "date not recorded"
        let title = changed ? "\(water.name): now a \(level.lowercased())" : "\(level): \(water.name)"
        let body = "Posted \(posted) in the state's records. No all-clear recorded. Open to see what it asks of people and pets."
        let id = "\(water.id)|\(status.tier?.rawValue ?? "-")|\(status.posted?.iso ?? "-")"
        return PlannedNotification(id: id, waterID: water.id, title: title, body: body)
    }
}
