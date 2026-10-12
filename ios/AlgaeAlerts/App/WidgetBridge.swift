import Foundation
import WidgetKit
import AlgaeCore

/// Writes the widget's digest into the App Group container and reloads the
/// widget only when the digest changed.
enum WidgetBridge {
    static let appGroup = "group.net.chelseakr.algaealerts"
    static let fileName = "widget-digest.json"

    static var fileURL: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroup)?.appendingPathComponent(fileName)
    }

    static func publish(_ digest: WidgetDigest) {
        guard let url = fileURL else { return }
        let store = JSONFileStore<WidgetDigest>(url: url)
        if let current = try? store.load(), current == digest { return }
        try? store.save(digest)
        WidgetCenter.shared.reloadAllTimelines()
    }
}
