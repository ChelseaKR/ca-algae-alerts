import SwiftUI
import AlgaeCore

struct AboutView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Harmful algal bloom advisories that California and Missouri have recorded for lakes, rivers and shorelines, with each water's history: California's since 2016, Missouri's since 2017.")
                    Text("For large lakes, a separately labeled satellite estimate from the U.S. EPA. It is never an advisory.")
                    Text("An advisory stays listed, with its date, until the state records an end.")
                } header: { SectionTitle("What this app shows") }
                Section {
                    Text("A lake with no advisory is not shown to be free of toxic algae. Most waters are never tested, and reports are voluntary.")
                    Text("An advisory is the state's recommendation; signs may or may not be posted at the water.")
                    Text("This app checks the state's data about once a day. Check posted signs and the official map before you go.")
                } header: { SectionTitle("What the records cannot tell you") }
                Section {
                    if env.isEntitled {
                        Label("Unlocked. Thank you.", systemImage: "checkmark.seal")
                    } else {
                        Text(FreeTier.unlockSummary)
                        Button("Unlock alerts and the widget") { router.showUnlock = true }
                    }
                    Button("Restore purchases") { Task { await env.purchases.restorePurchases() } }
                } header: { SectionTitle(FreeTier.purchaseName) }
                ForEach(env.snapshot?.sources ?? [], id: \.id) { source in
                    Section {
                        Text(source.agency)
                        Text(source.program).font(.footnote)
                        Text("License: \(source.license); \(source.rights).").font(.footnote)
                        Text(source.liftExplanation).font(.footnote)
                        Text(source.attribution).font(.footnote)
                        if !source.requiredDisclaimer.isEmpty {
                            Text(source.requiredDisclaimer).font(.caption2)
                        }
                        if source.revocable {
                            Text("The publisher may withdraw permission to use this data; if it does, this app removes it.").font(.caption2)
                        }
                        Link("The source's data", destination: URL(string: source.datasetUrl)!)
                    } header: { SectionTitle(source.recordKind == .satelliteEstimate ? "Satellite estimates" : "\(Waterbody.stateNames[source.state] ?? source.state) advisories") }
                }
                Section {
                    Text("Not affiliated with or endorsed by any state or federal agency.").font(.footnote)
                }
                Section {
                    Text("This app collects nothing: no account, no analytics, no tracking. Favorites stay on this iPhone. Its one network request downloads the public advisory file.")
                    Link("Privacy policy", destination: SnapshotEndpoint.siteURL.appendingPathComponent("privacy/"))
                } header: { SectionTitle("Privacy") }
                Section {
                    Link("Email support", destination: URL(string: "mailto:chelsea@chelseakr.com")!)
                    Button("Show the introduction again") { env.showIntroAgain() }
                } header: { SectionTitle("Help") }
            }
            .navigationTitle("About")
        }
    }
}
