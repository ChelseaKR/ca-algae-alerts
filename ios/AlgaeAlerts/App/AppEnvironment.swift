import Foundation
import Observation
import UserNotifications
import AlgaeCore

/// The app's state: the snapshot on the phone, favorites, mutes, the alert
/// baseline and the purchase. Views read it; it does every write.
@MainActor
@Observable
final class AppEnvironment {
    static var shared: AppEnvironment?

    let stores: AppStores
    let snapshotStore: SnapshotStore
    let refresher: SnapshotRefresher
    let purchases: PurchaseManager
    let notifications: NotificationScheduler
    private let launch: LaunchOptions

    private(set) var snapshot: Snapshot?
    private(set) var favorites: Favorites
    private(set) var muted: MutedWaters
    private(set) var introSeen: Bool
    private(set) var isRefreshing = false
    private(set) var lastCheckFailed: Bool
    private(set) var lastSuccess: Date?
    private(set) var notificationStatus: UNAuthorizationStatus = .notDetermined

    /// Test and screenshot switches, read from launch arguments. None of
    /// them exists in a normal launch.
    struct LaunchOptions {
        var uiTesting = false
        var skipIntro = false
        var entitled = false
        var favorites: [String] = []

        static func current(_ args: [String] = ProcessInfo.processInfo.arguments) -> LaunchOptions {
            var o = LaunchOptions()
            o.uiTesting = args.contains("-uiTesting")
            o.skipIntro = args.contains("-skipIntro")
            o.entitled = args.contains("-entitled")
            if let i = args.firstIndex(of: "-favorites"), i + 1 < args.count {
                o.favorites = args[i + 1].split(separator: ",").map(String.init)
            }
            return o
        }
    }

    init(layout: AppStorageLayout? = nil, bundled: URL? = Bundle.main.url(forResource: "snapshot", withExtension: "json"),
         session: URLSession = .shared, launch: LaunchOptions = .current()) {
        self.launch = launch
        let resolved = layout ?? Self.defaultLayout(uiTesting: launch.uiTesting)
        stores = AppStores(layout: resolved)
        snapshotStore = SnapshotStore(layout: resolved, bundled: bundled)
        refresher = SnapshotRefresher(session: session, store: snapshotStore)
        purchases = PurchaseManager(entitlementStore: EntitlementStore(layout: resolved))
        notifications = NotificationScheduler()
        snapshot = snapshotStore.load()
        favorites = stores.favorites()
        muted = stores.muted()
        introSeen = stores.intro().seen || launch.skipIntro
        let meta = snapshotStore.meta()
        lastCheckFailed = meta.lastAttemptFailed
        lastSuccess = meta.lastSuccess
        if launch.uiTesting {
            if launch.entitled { purchases.setEntitled(true) }
            if !launch.favorites.isEmpty { favorites = Favorites(ids: launch.favorites) }
        }
        purchases.onEntitlementChange = { [weak self] _ in self?.publishWidgetDigest() }
    }

    private static func defaultLayout(uiTesting: Bool) -> AppStorageLayout {
        if uiTesting {
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent("uitest-\(UUID().uuidString)")
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            return AppStorageLayout(directory: dir)
        }
        return (try? AppStorageLayout.applicationSupport()) ?? AppStorageLayout(directory: FileManager.default.temporaryDirectory)
    }

    var isEntitled: Bool { purchases.isEntitled }

    var today: PlainDate { PlainDate.today() }

    // MARK: Refresh

    func refreshIfDue() async {
        guard !launch.uiTesting, RefreshThrottle.isDue(snapshotStore.meta()) else { return }
        _ = await refreshNow()
    }

    @discardableResult
    func refreshNow() async -> RefreshOutcome {
        guard !isRefreshing else { return .notModified }
        isRefreshing = true
        defer { isRefreshing = false }
        let outcome = await refresher.refresh()
        await apply(outcome)
        return outcome
    }

    func performBackgroundRefresh() async -> RefreshOutcome {
        await refreshNow()
    }

    private func apply(_ outcome: RefreshOutcome) async {
        let meta = snapshotStore.meta()
        lastCheckFailed = meta.lastAttemptFailed
        lastSuccess = meta.lastSuccess
        if case .updated(let new) = outcome {
            snapshot = new
            await planAlerts(schedule: true)
        }
        publishWidgetDigest()
    }

    /// Replans for everyone, so the baseline is current; schedules only
    /// with the purchase, and never for a muted lake.
    func planAlerts(schedule: Bool) async {
        guard let snapshot else { return }
        let plan = AlertPlanner.plan(favorites: Set(favorites.ids), snapshot: snapshot, baseline: stores.baseline())
        try? stores.save(plan.baseline)
        guard schedule, FreeTier.notificationsAllowed(isEntitled: isEntitled) else { return }
        await notifications.schedule(muted.unmuted(plan.notifications))
    }

    // MARK: Favorites, mutes, intro

    func isFavorite(_ id: Waterbody.ID) -> Bool { favorites.contains(id) }

    func toggleFavorite(_ id: Waterbody.ID) {
        favorites.toggle(id)
        try? stores.save(favorites)
        Task { await planAlerts(schedule: false) }
        publishWidgetDigest()
    }

    func isMuted(_ id: Waterbody.ID) -> Bool { muted.contains(id) }

    func setMuted(_ id: Waterbody.ID, _ value: Bool) {
        if value { muted.mute(id) } else { muted.unmute(id) }
        try? stores.save(muted)
    }

    func finishIntro() {
        introSeen = true
        try? stores.save(IntroState(seen: true))
    }

    func showIntroAgain() { introSeen = false }

    // MARK: Notifications permission

    func refreshNotificationStatus() async {
        notificationStatus = await notifications.authorizationStatus()
    }

    func requestNotifications() async {
        await notifications.requestAuthorization()
        await refreshNotificationStatus()
    }

    // MARK: Widget

    func publishWidgetDigest() {
        WidgetBridge.publish(WidgetDigest.build(snapshot: snapshot, favorites: favorites, isEntitled: isEntitled, lastCheckFailed: lastCheckFailed))
    }
}
