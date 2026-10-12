import Foundation
import BackgroundTasks
import AlgaeCore

/// The app's `BGAppRefreshTask`. iOS decides when it runs, typically a few
/// times a day at most. That is honest here because the state republishes
/// its file about daily, and the app says "within about a day", never
/// "real time" (docs/DECISIONS.md 0006).
enum BackgroundRefresh {
    static let taskIdentifier = "net.chelseakr.algaealerts.refresh"

    static func register(_ work: @escaping @Sendable () async -> RefreshOutcome) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskIdentifier, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { task.setTaskCompleted(success: false); return }
            scheduleNextRefresh()
            let running = Task {
                let outcome = await work()
                switch outcome {
                case .updated, .notModified: refreshTask.setTaskCompleted(success: true)
                case .failed: refreshTask.setTaskCompleted(success: false)
                }
            }
            refreshTask.expirationHandler = { running.cancel() }
        }
    }

    static func scheduleNextRefresh(earliestIn seconds: TimeInterval = 8 * 60 * 60) {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: seconds)
        try? BGTaskScheduler.shared.submit(request)
    }
}
