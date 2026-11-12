import Foundation
import Network
import Observation

/// Whether this iPhone has a network path right now, so the lake list can
/// say it is showing the copy already on the phone, with its date. It never
/// hides data: offline, every screen still shows what is on the phone.
@MainActor
@Observable
final class ConnectionWatch {
    private(set) var isOffline: Bool
    @ObservationIgnored private var monitor: NWPathMonitor?

    /// `simulateOffline` is the UI tests' switch (`-simulateOffline`); it
    /// starts no monitor.
    init(simulateOffline: Bool) {
        isOffline = simulateOffline
        guard !simulateOffline else { return }
        let monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [weak self] path in
            let offline = path.status != .satisfied
            Task { @MainActor in self?.isOffline = offline }
        }
        monitor.start(queue: DispatchQueue(label: "net.chelseakr.algaealerts.connection", qos: .utility))
        self.monitor = monitor
    }

    deinit { monitor?.cancel() }
}
