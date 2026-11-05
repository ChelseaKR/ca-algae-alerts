import SwiftUI
import UIKit
import AlgaeCore

/// Colors with checked contrast in light and dark mode. Color is never the
/// only signal: every status also has words and a symbol.
enum Theme {
    /// The system label color, by value. `.primary` is hierarchical, and in
    /// a list section header it resolves to the header's own gray, which
    /// the accessibility audit flags as low contrast.
    static let label = Color(uiColor: .label)

    /// Secondary text darker than the system's: 8.8:1 on white, 7.9:1 on the
    /// grouped-list gray; 12.5:1 on black, 10.1:1 on a dark list cell. The
    /// system's secondary gray falls just short of the accessibility audit
    /// at body sizes.
    static let secondaryText = Color(UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 0.78, green: 0.78, blue: 0.80, alpha: 1)
        : UIColor(red: 0.29, green: 0.29, blue: 0.31, alpha: 1) })

    /// Deep amber: 6.9:1 on white, 6.2:1 on the grouped-list gray; light amber
    /// on dark: 11.5:1 on black, 9.3:1 on a dark list cell. `ThemeContrastTests`.
    static let advisory = Color(UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 0.94, green: 0.71, blue: 0.35, alpha: 1)
        : UIColor(red: 0.54, green: 0.29, blue: 0.0, alpha: 1) })

    /// Lake teal, the app's accent: 7.8:1 on white, 12.2:1 on black.
    static let accent = Color(UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 0.50, green: 0.82, blue: 0.92, alpha: 1)
        : UIColor(red: 0.03, green: 0.35, blue: 0.45, alpha: 1) })

    static func symbol(for status: Status) -> String {
        switch status.kind {
        case .advisory: "exclamationmark.triangle.fill"
        case .noAdvisoryRecorded: "doc.text"
        case .undetermined: "questionmark.circle"
        }
    }

    static func tint(for status: Status) -> Color {
        status.kind == .advisory ? advisory : secondaryText
    }
}

/// One status line with its symbol, for list rows.
struct StatusLine: View {
    let status: Status

    var body: some View {
        Label {
            Text(StatusWording.shortLine(status))
        } icon: {
            Image(systemName: Theme.symbol(for: status)).foregroundStyle(Theme.tint(for: status))
        }
        .font(.subheadline)
        .foregroundStyle(status.kind == .advisory ? Theme.advisory : Theme.secondaryText)
    }
}

struct LakeRow: View {
    let water: Waterbody
    let isFavorite: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(water.name).font(.headline)
                if isFavorite {
                    Image(systemName: "star.fill").foregroundStyle(Theme.accent).accessibilityLabel("Favorite")
                }
            }
            Text(water.countyLabel).font(.subheadline).foregroundStyle(Theme.secondaryText)
            StatusLine(status: water.status)
            // The same notes the website's advisory lists carry (0017).
            ForEach([StatusWording.newerPosting(water), StatusWording.olderHigher(water)].compactMap { $0 }, id: \.self) { note in
                Text(note).font(.footnote).foregroundStyle(Theme.secondaryText)
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
    }
}

/// A list section's title in the label color. The system's gray header
/// falls just short of the accessibility audit's contrast check at this size.
struct SectionTitle: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text).foregroundStyle(Theme.label).font(.footnote.weight(.semibold))
    }
}
