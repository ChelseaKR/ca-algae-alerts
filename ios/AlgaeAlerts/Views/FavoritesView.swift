import SwiftUI
import AlgaeCore

struct FavoritesView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router

    var body: some View {
        NavigationStack {
            List {
                alertsSection
                if env.favorites.ids.isEmpty {
                    Section {
                        Text("Tap the star on a lake to keep it here.").foregroundStyle(Theme.secondaryText)
                    }
                } else {
                    Section {
                        ForEach(env.favorites.ids, id: \.self) { id in
                            if let water = env.snapshot?.waterbody(id: id) {
                                NavigationLink(value: id) { LakeRow(water: water, isFavorite: false) }
                            } else {
                                VStack(alignment: .leading) {
                                    Text("A saved lake").font(.headline)
                                    Text("No longer in the state's current file.").font(.subheadline).foregroundStyle(Theme.secondaryText)
                                }
                            }
                        }
                    } header: { SectionTitle("Your lakes") }
                }
            }
            .navigationTitle("Favorites")
            .navigationDestination(for: Waterbody.ID.self) { id in LakeDetailView(id: id) }
            .task { await env.refreshNotificationStatus() }
        }
    }

    @ViewBuilder
    private var alertsSection: some View {
        Section {
            if !env.isEntitled {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Alerts and the widget").font(.headline)
                    Text(FreeTier.unlockSummary).font(.subheadline)
                    Button("See the one-time unlock") { router.showUnlock = true }
                        .accessibilityIdentifier("open-unlock")
                }
            } else if env.notificationStatus == .notDetermined {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Turn on alerts").font(.headline)
                    Text("When a favorite lake gets a new advisory in the state's records, this iPhone shows an alert when iOS lets Lake Notice check, often within a day of the state publishing it. Alerts are not real time. Alerts are made on this iPhone; nothing about you is sent anywhere.")
                        .font(.subheadline)
                    Button("Turn on alerts") { Task { await env.requestNotifications() } }
                }
            } else if env.notificationStatus == .denied {
                Text("Alerts are off in Settings for this app. Favorites still update here.").font(.subheadline)
            } else {
                Label("Alerts are on for your favorites", systemImage: "bell")
            }
        }
    }
}
