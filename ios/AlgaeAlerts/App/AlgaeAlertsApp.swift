import SwiftUI
import BackgroundTasks

@main
struct AlgaeAlertsApp: App {
    @State private var environment = AppEnvironment()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        // Before launch finishes: the background task must be registered
        // and the notification delegate set, so a tap that launched the app
        // is delivered.
        AppEnvironment.shared = environment
        BackgroundRefresh.register { await AppEnvironment.shared?.performBackgroundRefresh() ?? .failed("no environment") }
        NotificationResponder.shared.install()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
                .environment(AppRouter.shared)
                .onOpenURL { AppRouter.shared.handle($0) }
                .task { await refreshOnOpen() }
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                Task { await refreshOnOpen() }
            case .background:
                BackgroundRefresh.scheduleNextRefresh()
                environment.publishWidgetDigest()
            default:
                break
            }
        }
    }

    private func refreshOnOpen() async {
        guard ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] == nil else { return }
        await environment.refreshIfDue()
        await environment.refreshNotificationStatus()
    }
}
