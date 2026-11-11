import SwiftUI
import AlgaeCore

struct FavoritesView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router

    var body: some View {
        NavigationStack {
            List {
                if env.favorites.ids.isEmpty {
                    Section {
                        NoticeBoard(
                            title: EmptyCopy.noFavoritesTitle, message: EmptyCopy.noFavoritesMessage,
                            systemImage: "star",
                            actionTitle: "Browse lakes", actionID: "browse-lakes",
                            action: { router.tab = .advisories })
                    }
                    .listRowInsets(EdgeInsets(top: 0, leading: 0, bottom: 0, trailing: 0))
                    .listRowBackground(Theme.paper)
                }
                alertsSection
                if !env.favorites.ids.isEmpty {
                    Section {
                        ForEach(env.favorites.ids, id: \.self) { id in
                            if let water = env.snapshot?.waterbody(id: id) {
                                NavigationLink(value: id) { LakeRow(water: water, isFavorite: false) }
                            } else {
                                // Absence is not a status (DECISIONS 0039).
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(SavedLakeCopy.title).font(.headline)
                                    Text(SavedLakeCopy.detail(id: id, snapshot: env.snapshot)).font(.subheadline).foregroundStyle(Theme.secondaryText)
                                }
                                .accessibilityElement(children: .combine)
                            }
                        }
                    } header: { SectionTitle("Your lakes") }
                    .surfaceRows()
                }
            }
            .noticeList()
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
        .surfaceRows()
    }
}
