import SwiftUI
import AlgaeCore

/// First launch: what the app shows, what it cannot tell you, and what the
/// unlock adds. Asks for no permission.
struct IntroView: View {
    @Environment(AppEnvironment.self) private var env

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Image(systemName: "drop.triangle")
                    .font(.system(size: 48))
                    .foregroundStyle(Theme.accent)
                    .accessibilityHidden(true)
                Text("Toxic algae advisories for lakes and rivers").font(.largeTitle.bold())
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
                    Text("Start browsing").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.accent)
                .accessibilityIdentifier("start-browsing")
            }
            .padding(24)
        }
    }

    private func point(_ symbol: String, _ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: symbol).font(.title2).foregroundStyle(Theme.accent).frame(width: 32).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(body)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
