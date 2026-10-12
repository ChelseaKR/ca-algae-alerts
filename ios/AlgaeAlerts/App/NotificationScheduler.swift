import Foundation
import UserNotifications
import AlgaeCore

/// Local notifications only: no push service, no device token. Everything
/// in an alert is built on the phone from the snapshot already on disk.
struct NotificationScheduler {
    let center: UNUserNotificationCenter
    init(center: UNUserNotificationCenter = .current()) { self.center = center }

    func authorizationStatus() async -> UNAuthorizationStatus {
        await center.notificationSettings().authorizationStatus
    }

    /// Called only after the app has said, in its own words, what alerts
    /// are and are not. Never at launch.
    @discardableResult
    func requestAuthorization() async -> Bool {
        (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
    }

    /// The alert's "Mute this lake" button. Registered at every launch.
    func registerCategories() {
        let mute = UNNotificationAction(identifier: AdvisoryAlertAction.muteIdentifier,
                                        title: AdvisoryAlertAction.muteTitle,
                                        options: [],
                                        icon: UNNotificationActionIcon(systemImageName: "bell.slash"))
        let category = UNNotificationCategory(identifier: AdvisoryAlertAction.categoryIdentifier,
                                              actions: [mute], intentIdentifiers: [], options: [])
        center.setNotificationCategories([category])
    }

    func schedule(_ notifications: [PlannedNotification]) async {
        for n in notifications {
            let content = UNMutableNotificationContent()
            content.title = n.title
            content.body = n.body
            content.sound = .default
            content.userInfo = n.userInfo
            content.threadIdentifier = n.waterID
            content.categoryIdentifier = AdvisoryAlertAction.categoryIdentifier
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
            try? await center.add(UNNotificationRequest(identifier: n.id, content: content, trigger: trigger))
        }
    }
}

/// Opens the lake an alert names, and saves a mute from its button.
final class NotificationResponder: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationResponder()

    func install() {
        UNUserNotificationCenter.current().delegate = self
        NotificationScheduler().registerCategories()
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let id = WaterLink.waterID(fromNotificationUserInfo: response.notification.request.content.userInfo) else { return }
        await MainActor.run {
            if response.actionIdentifier == AdvisoryAlertAction.muteIdentifier {
                AppEnvironment.shared?.setMuted(id, true)
            } else {
                AppRouter.shared.open(.water(id))
            }
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }
}
