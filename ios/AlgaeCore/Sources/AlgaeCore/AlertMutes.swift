import Foundation

/// Favorites whose alerts the person turned off, from an alert's button or
/// the switch on a lake's screen. A muted lake stays a favorite and keeps
/// its baseline, so unmuting announces only what is new after that.
public struct MutedWaters: Codable, Equatable, Sendable {
    public private(set) var ids: Set<Waterbody.ID>
    public init(ids: Set<Waterbody.ID> = []) { self.ids = ids }
    public func contains(_ id: Waterbody.ID) -> Bool { ids.contains(id) }
    public mutating func mute(_ id: Waterbody.ID) { ids.insert(id) }
    public mutating func unmute(_ id: Waterbody.ID) { ids.remove(id) }

    public func unmuted(_ notifications: [PlannedNotification]) -> [PlannedNotification] {
        notifications.filter { !ids.contains($0.waterID) }
    }
}

/// The button an advisory alert carries. Identifiers never change once
/// shipped: iOS stores them with the registered categories.
public enum AdvisoryAlertAction {
    public static let categoryIdentifier = "ALGAE_ADVISORY_ALERT"
    public static let muteIdentifier = "mute"
    public static let muteTitle = "Mute this lake"
}
