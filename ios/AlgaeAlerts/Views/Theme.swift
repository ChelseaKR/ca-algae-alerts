import SwiftUI
import UIKit
import AlgaeCore

/// Lake Notice's identity in the app (DECISIONS 0036): the website's tokens
/// (docs/DESIGN.md, 0035) as asset-catalog colors with light and dark
/// variants. Paper and deep-lake indigo ink, and California's posted-sign
/// colors for advisory levels only. Nothing here is green: no color in this
/// app says a water is safe. Color is never the only signal: every level
/// also has its words and its rank marks.
enum Theme {
    static let paper = Color("Paper")
    static let surface = Color("Surface")
    static let ink = Color("Ink")
    static let muted = Color("Muted")
    static let brand = Color("Brand")
    static let rule = Color("Rule")
    /// Links, buttons and the tab tint.
    static let link = Color("AccentColor")

    /// Older names, kept so every screen reads the same tokens.
    static let label = ink
    static let secondaryText = muted
    static let accent = link

    static func band(_ paint: NoticeBand.Paint) -> Color { Color(bandName(paint)) }
    static func bandInk(_ paint: NoticeBand.Paint) -> Color { Color(bandInkName(paint)) }

    static func bandName(_ paint: NoticeBand.Paint) -> String {
        switch paint {
        case .caution: "CautionBand"
        case .warning: "WarningBand"
        case .danger: "DangerBand"
        case .otherAdvisory: "OtherBand"
        case .record: "RecordBand"
        }
    }

    static func bandInkName(_ paint: NoticeBand.Paint) -> String {
        bandName(paint).replacingOccurrences(of: "Band", with: "Ink")
    }

    static func symbol(for status: Status) -> String {
        switch status.kind {
        case .advisory: "exclamationmark.triangle.fill"
        case .noAdvisoryRecorded: "doc.text"
        case .undetermined: "questionmark.circle"
        }
    }

    /// Navigation titles in the signage face: the system sans at its
    /// condensed width, scaled with Dynamic Type, in the brand ink.
    static func styleNavigationBars() {
        func face(_ style: UIFont.TextStyle, _ size: CGFloat, _ weight: UIFont.Weight) -> UIFont {
            UIFontMetrics(forTextStyle: style).scaledFont(for: .systemFont(ofSize: size, weight: weight, width: .condensed))
        }
        let brand = UIColor(named: "Brand") ?? .label
        let appearance = UINavigationBarAppearance()
        appearance.configureWithDefaultBackground()
        appearance.largeTitleTextAttributes = [.font: face(.largeTitle, 34, .heavy), .foregroundColor: brand]
        appearance.titleTextAttributes = [.font: face(.headline, 18, .bold), .foregroundColor: brand]
        let bar = UINavigationBar.appearance()
        bar.standardAppearance = appearance
        bar.compactAppearance = appearance
        bar.scrollEdgeAppearance = appearance
    }
}

extension Font {
    /// The signage face for headings, bands and section titles: the system
    /// sans, condensed, so it scales with Dynamic Type and needs no font file.
    static func signage(_ style: Font.TextStyle, weight: Font.Weight = .bold) -> Font {
        .system(style, weight: weight).width(.condensed)
    }
}

extension View {
    /// A list on the app's paper, not the system's gray.
    func noticeList() -> some View {
        scrollContentBackground(.hidden).background(Theme.paper)
    }

    /// Rows on the app's surface color.
    func surfaceRows() -> some View { listRowBackground(Theme.surface) }
}

/// One status line with its symbol, for list rows.
struct StatusLine: View {
    let status: Status

    var body: some View {
        Label {
            Text(StatusWording.shortLine(status))
        } icon: {
            Image(systemName: Theme.symbol(for: status))
        }
        .font(.subheadline)
        .foregroundStyle(status.kind == .advisory ? Theme.ink : Theme.muted)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(StatusWording.spokenShortLine(status))
    }
}

/// A date beside a value at normal sizes, stacked at accessibility sizes,
/// where side by side squeezes both.
struct DateValueRow<Leading: View, Trailing: View>: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @ViewBuilder let leading: Leading
    @ViewBuilder let trailing: Trailing

    var body: some View {
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 2))
            : AnyLayout(HStackLayout(alignment: .firstTextBaseline))
        layout {
            leading
            if !dynamicTypeSize.isAccessibilitySize { Spacer(minLength: 8) }
            trailing
        }
    }
}

/// A lake in a list: its posted-sign chip first, as a person meets it at
/// the shore, then the name, county and dated status.
struct LakeRow: View {
    let water: Waterbody
    let isFavorite: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            SignChip(band: NoticeBand(water.status))
            HStack(alignment: .firstTextBaseline) {
                Text(water.name).font(.headline).foregroundStyle(Theme.ink)
                if isFavorite {
                    Image(systemName: "star.fill").foregroundStyle(Theme.link).accessibilityLabel("Favorite")
                }
            }
            Text(water.countyLabel).font(.subheadline).foregroundStyle(Theme.muted)
            StatusLine(status: water.status)
            // The same notes the website's advisory lists carry (0017).
            ForEach([StatusWording.newerPosting(water), StatusWording.olderHigher(water)].compactMap { $0 }, id: \.self) { note in
                Text(note).font(.footnote).foregroundStyle(Theme.muted)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

/// A list section's title in the signage face, under a short brand rule:
/// the website's "depth mark" over each section.
struct SectionTitle: View {
    let text: String
    let systemImage: String?
    init(_ text: String, systemImage: String? = nil) {
        self.text = text
        self.systemImage = systemImage
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Rectangle().fill(Theme.brand).frame(width: 28, height: 4).accessibilityHidden(true)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                if let systemImage { Image(systemName: systemImage).accessibilityHidden(true) }
                Text(text)
            }
            .font(.signage(.subheadline))
            .tracking(0.6)
            .textCase(.uppercase)
            .foregroundStyle(Theme.ink)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(text)
        .accessibilityAddTraits(.isHeader)
    }
}
