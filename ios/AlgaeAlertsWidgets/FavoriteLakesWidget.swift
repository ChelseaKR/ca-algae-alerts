import SwiftUI
import WidgetKit
import AlgaeCore

/// "Favorite lakes": reads the digest the app writes into the App Group
/// container and nothing else. No network request, ever.
struct DigestEntry: TimelineEntry {
    let date: Date
    let digest: WidgetDigest?
}

struct DigestProvider: TimelineProvider {
    static let appGroup = "group.net.chelseakr.algaealerts"

    func load() -> WidgetDigest? {
        guard let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: Self.appGroup)?
            .appendingPathComponent("widget-digest.json") else { return nil }
        return (try? JSONFileStore<WidgetDigest>(url: url).load()) ?? nil
    }

    func placeholder(in context: Context) -> DigestEntry { DigestEntry(date: Date(), digest: nil) }

    func getSnapshot(in context: Context, completion: @escaping (DigestEntry) -> Void) {
        completion(DigestEntry(date: Date(), digest: load()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<DigestEntry>) -> Void) {
        // The app reloads the widget when its digest changes; this is a
        // fallback so a stale digest is re-read twice a day.
        completion(Timeline(entries: [DigestEntry(date: Date(), digest: load())], policy: .after(Date().addingTimeInterval(12 * 3600))))
    }
}

struct FavoriteLakesView: View {
    @Environment(\.widgetFamily) private var family
    let entry: DigestEntry

    var body: some View {
        Group {
            if let digest = entry.digest {
                if digest.locked { locked(digest) } else { favorites(digest) }
            } else {
                Text("Open the app to load the state's advisory data here.").font(.caption)
            }
        }
        // Capped like Queer Frame's widget: past this size the status words
        // and dates are cut off in a widget's fixed frame.
        .dynamicTypeSize(...DynamicTypeSize.xxLarge)
        .containerBackground(.fill.tertiary, for: .widget)
    }

    @ViewBuilder
    private func locked(_ digest: WidgetDigest) -> some View {
        if family == .accessoryInline {
            // The inline slot shows only one line of text.
            Text("Favorite lakes: part of full access")
                .widgetURL(WaterLink.unlockURL)
        } else {
            lockedBlock(digest)
        }
    }

    @ViewBuilder
    private func lockedBlock(_ digest: WidgetDigest) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Favorite lakes").font(.headline)
            Text("Part of full access.").font(.caption)
            if let date = digest.fileDate {
                Text("\(digest.advisoryCount) waters with an advisory on file, state data \(date.label).").font(.caption2)
            }
        }
        .widgetURL(WaterLink.unlockURL)
    }

    @ViewBuilder
    private func favorites(_ digest: WidgetDigest) -> some View {
        let limit = family == .systemMedium ? 3 : (family == .systemLarge ? 6 : 1)
        if digest.rows.isEmpty {
            Text("Star a lake in the app to see it here.").font(.caption)
        } else if family == .accessoryInline, let row = digest.rows.first {
            Text("\(row.name): \(row.line)")
                .accessibilityLabel("\(row.name): \(row.spokenLine)")
                .widgetURL(WaterLink.url(for: row.id))
        } else {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(digest.rows.prefix(limit), id: \.id) { row in
                    Link(destination: WaterLink.url(for: row.id)) {
                        // The status line gets its two lines before the
                        // name gets a second: the level and date are the point.
                        VStack(alignment: .leading, spacing: 1) {
                            Text(row.name).font(.caption.bold()).lineLimit(family == .systemSmall ? 2 : 1)
                            Text(row.line).font(.caption2).lineLimit(2)
                                .layoutPriority(1)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(row.name), \(row.spokenLine)")
                    }
                }
                if digest.missingFavorites > 0 {
                    Text("\(digest.missingFavorites) saved lake(s) not in the current data").font(.caption2)
                }
                if digest.lastCheckFailed {
                    Text("Last check did not finish").font(.caption2)
                }
            }
            .widgetURL(WaterLink.url(for: digest.rows[0].id))
        }
    }
}

struct FavoriteLakesWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "FavoriteLakes", provider: DigestProvider()) { entry in
            FavoriteLakesView(entry: entry)
        }
        .configurationDisplayName("Favorite lakes")
        .description("The latest state record for your favorite lakes, with its date.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline])
    }
}

@main
struct AlgaeAlertsWidgets: WidgetBundle {
    var body: some Widget { FavoriteLakesWidget() }
}
