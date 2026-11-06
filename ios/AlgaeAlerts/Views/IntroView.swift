import SwiftUI
import AlgaeCore

/// First launch: what the app shows, what it cannot tell you, and what the
/// unlock adds. Asks for no permission.
struct IntroView: View {
    @Environment(AppEnvironment.self) private var env

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Wordmark()
                // The three posted signs, in order, as a person meets them
                // at the shore. Each says its words; the marks give the rank.
                VStack(spacing: 6) {
                    ForEach([AdvisoryTier.caution, .warning, .danger], id: \.self) { tier in
                        SignBand(band: NoticeBand(Status(kind: .advisory, tier: tier)))
                            .overlay(Rectangle().strokeBorder(Theme.ink, lineWidth: tier == .danger ? 3 : 2))
                    }
                }
                Text("Toxic algae advisories for lakes and rivers")
                    .font(.signage(.largeTitle, weight: .heavy))
                    .foregroundStyle(Theme.ink)
                    .accessibilityAddTraits(.isHeader)
                point("list.bullet.rectangle", "What the state has recorded",
                      CoverageCopy.introSummary(env.snapshot))
                point("calendar", "Every status has a date",
                      "An advisory stays listed until the state records an end. Old ones say so, with their date.")
                point("exclamationmark.bubble", "What the records cannot tell you",
                      "No advisory does not mean no algae. Most waters are never tested. Check signs at the water.")
                point("bell", "Alerts and widget: a one-time unlock",
                      "Browsing is free. Alerts for your favorite lakes and the widget are one purchase.")
                Button {
                    env.finishIntro()
                } label: {
                    Text("Start browsing").font(.headline).frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.link)
                .foregroundStyle(Theme.paper)
                .accessibilityIdentifier("start-browsing")
            }
            .padding(24)
        }
        .background(Theme.paper)
    }

    private func point(_ symbol: String, _ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: symbol).font(.title2).foregroundStyle(Theme.brand).frame(width: 32).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.signage(.title3)).foregroundStyle(Theme.ink)
                Text(body).foregroundStyle(Theme.ink)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
