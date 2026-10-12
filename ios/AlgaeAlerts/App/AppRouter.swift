import Foundation
import Observation
import AlgaeCore

/// Where a link, a widget tap or an alert tap wants to go.
@MainActor
@Observable
final class AppRouter {
    static let shared = AppRouter()

    enum Tab: Hashable { case advisories, favorites, about }

    var tab: Tab = .advisories
    var openWater: Waterbody.ID?
    var showUnlock = false

    func open(_ destination: WaterLink.Destination) {
        switch destination {
        case .water(let id):
            tab = .advisories
            openWater = id
        case .unlock:
            showUnlock = true
        }
    }

    func handle(_ url: URL) {
        if let destination = WaterLink.destination(for: url) { open(destination) }
    }
}
