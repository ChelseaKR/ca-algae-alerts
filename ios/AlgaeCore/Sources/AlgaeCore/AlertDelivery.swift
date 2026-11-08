import Foundation

/// Every alert this phone has handed to iOS, by its key: the water, the
/// level and the posted date (`PlannedNotification.id`). Saved to its own
/// file so it survives a relaunch and a new snapshot (DECISIONS 0031).
///
/// The baseline alone cannot stop a repeat: if a short or broken file drops
/// an advisory and the next file brings it back, the baseline sees "no
/// advisory, then advisory" and plans the same alert again. A key that was
/// delivered once is never delivered again. A new posting has a new date,
/// and a new level has a new tier, so either still alerts.
public struct DeliveredAlerts: Codable, Equatable, Sendable {
    public private(set) var keys: Set<String>
    public init(keys: Set<String> = []) { self.keys = keys }

    public func contains(_ key: String) -> Bool { keys.contains(key) }
    public mutating func record(_ key: String) { keys.insert(key) }

    /// The planned alerts that have never been delivered, each key once even
    /// if the plan carries it twice.
    public func undelivered(_ planned: [PlannedNotification]) -> [PlannedNotification] {
        var seen = keys
        return planned.filter { seen.insert($0.id).inserted }
    }
}

extension AppStorageLayout {
    public var deliveredFile: URL { directory.appendingPathComponent("delivered-alerts.json") }
}

extension AppStores {
    /// A missing or unreadable file reads as empty. That can only allow an
    /// alert, never hide a new one.
    public func delivered() -> DeliveredAlerts {
        ((try? JSONFileStore<DeliveredAlerts>(url: layout.deliveredFile).load()) ?? nil) ?? DeliveredAlerts()
    }

    public func save(_ value: DeliveredAlerts) throws { try JSONFileStore(url: layout.deliveredFile).save(value) }
}
