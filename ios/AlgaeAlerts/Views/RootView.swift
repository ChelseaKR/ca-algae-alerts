import SwiftUI
import AlgaeCore

struct RootView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router

    var body: some View {
        @Bindable var router = router
        TabView(selection: $router.tab) {
            AdvisoriesView()
                .tabItem { Label("Lakes", systemImage: "drop") }
                .tag(AppRouter.Tab.advisories)
            FavoritesView()
                .tabItem { Label("Favorites", systemImage: "star") }
                .tag(AppRouter.Tab.favorites)
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
                .tag(AppRouter.Tab.about)
        }
        .tint(Theme.accent)
        .sheet(isPresented: $router.showUnlock) { PurchaseView() }
        .fullScreenCover(isPresented: Binding(get: { !env.introSeen }, set: { if !$0 { env.finishIntro() } })) {
            IntroView()
        }
    }
}
