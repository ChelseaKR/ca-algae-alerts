import Foundation

/// What the one-time purchase unlocks (docs/DECISIONS.md 0001). Browsing,
/// search, favorites and every lake's history are free, and never worse
/// than the free website. Alerts and the widget need the purchase.
public enum FreeTier {
    public static let widgetsRequireFullAccess = true

    public static func notificationsAllowed(isEntitled: Bool) -> Bool { isEntitled }

    public static func widgetUnlocked(isEntitled: Bool) -> Bool {
        !widgetsRequireFullAccess || isEntitled
    }

    /// The words every unlock surface uses for what the purchase includes.
    public static let unlockSummary = "Alerts when a favorite lake gets a new advisory, and a Home Screen and Lock Screen widget for your favorites."
}
