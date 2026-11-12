import SwiftUI
import AlgaeCore

// The posted-notice pieces (DECISIONS 0036): the mark, the sign band with
// its rank marks, the notice card a lake's status sits in, and the notice
// board the empty and offline screens use. They follow the website's
// docs/DESIGN.md: words first, a shape second, color third.

/// The Lake Notice mark: a notice board on a post at the waterline, with
/// ripples. Drawn from the website's `mark.svg` on its 32-unit grid, in its
/// fixed colors, so it reads the same as the favicon in either appearance.
struct NoticeMark: View {
    private static let indigo = Color(red: 0x26 / 255, green: 0x2a / 255, blue: 0x6b / 255)
    private static let board = Color(red: 0xfb / 255, green: 0xfa / 255, blue: 0xf6 / 255)
    private static let header = Color(red: 0x8f / 255, green: 0x95 / 255, blue: 0xe8 / 255)

    var body: some View {
        Canvas { context, size in
            let u = min(size.width, size.height) / 32
            func box(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect {
                CGRect(x: x * u, y: y * u, width: w * u, height: h * u)
            }
            func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * u, y: y * u) }
            context.fill(Path(roundedRect: box(0, 0, 32, 32), cornerRadius: 6 * u), with: .color(Self.indigo))
            context.fill(Path(roundedRect: box(6, 4, 20, 13), cornerRadius: 1.5 * u), with: .color(Self.board))
            context.fill(Path(roundedRect: box(6, 4, 20, 4.5), cornerRadius: 1.5 * u), with: .color(Self.header))
            var lines = Path()
            lines.move(to: pt(10, 12)); lines.addLine(to: pt(22, 12))
            lines.move(to: pt(10, 14.6)); lines.addLine(to: pt(18, 14.6))
            context.stroke(lines, with: .color(Self.indigo), style: StrokeStyle(lineWidth: 1.4 * u, lineCap: .round))
            var post = Path()
            post.move(to: pt(16, 17)); post.addLine(to: pt(16, 23))
            context.stroke(post, with: .color(Self.board), lineWidth: 2.2 * u)
            var ripple = Path()
            ripple.move(to: pt(4, 25))
            ripple.addCurve(to: pt(10, 25), control1: pt(6, 23.6), control2: pt(8, 23.6))
            ripple.addCurve(to: pt(16, 25), control1: pt(12, 26.4), control2: pt(14, 26.4))
            ripple.addCurve(to: pt(22, 25), control1: pt(18, 23.6), control2: pt(20, 23.6))
            ripple.addCurve(to: pt(28, 25), control1: pt(24, 26.4), control2: pt(26, 26.4))
            context.stroke(ripple, with: .color(Self.board), style: StrokeStyle(lineWidth: 1.8 * u, lineCap: .round))
        }
        .aspectRatio(1, contentMode: .fit)
    }
}

/// The mark beside the name, in the signage face. Spoken once, as the name.
struct Wordmark: View {
    @ScaledMetric(relativeTo: .title2) private var markSize: CGFloat = 36

    var body: some View {
        HStack(spacing: 10) {
            NoticeMark().frame(width: markSize, height: markSize)
            Text("Lake Notice")
                .font(.signage(.title2, weight: .heavy))
                .tracking(0.5)
                .foregroundStyle(Theme.brand)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Lake Notice")
        .accessibilityAddTraits(.isHeader)
    }
}

/// One to three filled squares: the level's rank on California's scale.
struct RankMarks: View {
    let rank: Int
    let size: CGFloat

    var body: some View {
        HStack(spacing: size * 0.35) {
            ForEach(0..<NoticeBand.rankCount, id: \.self) { i in
                Rectangle()
                    .fill(i < rank ? AnyShapeStyle(.foreground) : AnyShapeStyle(.clear))
                    .overlay(Rectangle().strokeBorder(.foreground, lineWidth: max(1.5, size / 6)))
                    .frame(width: size, height: size)
            }
        }
        .accessibilityHidden(true)
    }
}

/// The band across the top of a posted notice: the level's words in
/// capitals, and its rank marks. At accessibility text sizes the marks go
/// under the words, so neither is squeezed.
struct SignBand: View {
    let band: NoticeBand
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @ScaledMetric(relativeTo: .headline) private var markSize: CGFloat = 12

    var body: some View {
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 6))
            : AnyLayout(HStackLayout(alignment: .center, spacing: 12))
        layout {
            Text(band.words)
                .font(.signage(.headline, weight: .heavy))
                .tracking(1.4)
                .textCase(.uppercase)
                .fixedSize(horizontal: false, vertical: true)
            if !dynamicTypeSize.isAccessibilitySize { Spacer(minLength: 0) }
            if let rank = band.rank { RankMarks(rank: rank, size: markSize) }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.bandInk(band.paint))
        .background(Theme.band(band.paint))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(band.spoken)
        .accessibilityIdentifier("lake-sign")
    }
}

/// The small form of the band for list rows.
struct SignChip: View {
    let band: NoticeBand
    @ScaledMetric(relativeTo: .caption) private var markSize: CGFloat = 8

    var body: some View {
        HStack(spacing: 8) {
            Text(band.words)
                .font(.signage(.caption, weight: .heavy))
                .tracking(1)
                .textCase(.uppercase)
                .fixedSize(horizontal: false, vertical: true)
            if let rank = band.rank { RankMarks(rank: rank, size: markSize) }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .foregroundStyle(Theme.bandInk(band.paint))
        .background(Theme.band(band.paint))
        .overlay {
            Rectangle().strokeBorder(Theme.ink, style: StrokeStyle(lineWidth: 1, dash: band.isAdvisory ? [] : [4, 3]))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(band.spoken)
    }
}

/// A lake's status drawn as the notice posted at the shore: the band, a
/// rule, then the record. Danger gets the heavier edge; anything that is
/// not an advisory gets a dashed edge and the neutral band.
struct NoticeCard<Content: View>: View {
    let band: NoticeBand
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SignBand(band: band)
            Rectangle().fill(Theme.ink).frame(height: 2).accessibilityHidden(true)
            content
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay {
            RoundedRectangle(cornerRadius: 4).strokeBorder(
                Theme.ink,
                style: StrokeStyle(lineWidth: band.heavyEdge ? 3 : 2, dash: band.isAdvisory ? [] : [7, 4]))
        }
    }
}

/// A blank notice board for a screen with nothing to show: what happened,
/// in words, and the one thing to do next.
struct NoticeBoard: View {
    let title: String
    let message: String
    var systemImage: String? = nil
    var actionTitle: String? = nil
    var actionID: String? = nil
    var action: (() -> Void)? = nil
    @ScaledMetric(relativeTo: .largeTitle) private var markSize: CGFloat = 52

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center, spacing: 12) {
                NoticeMark().frame(width: markSize, height: markSize).accessibilityHidden(true)
                if let systemImage {
                    Image(systemName: systemImage).font(.title).foregroundStyle(Theme.brand).accessibilityHidden(true)
                }
            }
            Text(title)
                .font(.signage(.title2, weight: .heavy))
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text(message)
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle).font(.headline).frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.link)
                .foregroundStyle(Theme.paper)
                .accessibilityIdentifier(actionID ?? "")
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface)
        .overlay {
            RoundedRectangle(cornerRadius: 4).strokeBorder(Theme.muted, style: StrokeStyle(lineWidth: 2, dash: [7, 4]))
        }
    }
}

/// A `NoticeBoard` filling a screen, on the paper, scrolling at large text.
struct NoticeEmptyState: View {
    let board: NoticeBoard

    var body: some View {
        ScrollView {
            board.padding(20)
        }
        .background(Theme.paper)
    }
}
