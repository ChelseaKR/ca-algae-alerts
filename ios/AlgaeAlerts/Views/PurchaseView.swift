import SwiftUI
import StoreKit
import AlgaeCore

struct PurchaseView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(FreeTier.purchaseName).font(.signage(.title2, weight: .heavy)).foregroundStyle(Theme.ink)
                        Text(FreeTier.unlockSummary)
                        Text("One purchase, no subscription. Browsing, search, favorites and every lake's history stay free.")
                            .font(.subheadline).foregroundStyle(Theme.secondaryText)
                    }
                    .padding(.vertical, 4)
                }
                .surfaceRows()
                Section {
                    Text("Your iPhone checks the state's data in the background when iOS lets it, often within a day of the state publishing, and alerts you when a favorite lake gets a new advisory or its level changes. Alerts are not real time.")
                    Text("An alert is never an all-clear: the app does not send one when an advisory ends.")
                } header: { SectionTitle("How alerts work") }
                .surfaceRows()
                Section {
                    if env.purchases.isEntitled {
                        Label("Unlocked", systemImage: "checkmark.seal")
                    } else {
                        Button {
                            Task { await env.purchases.purchase() }
                        } label: {
                            Text(buyTitle).font(.headline).frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Theme.link)
                        .foregroundStyle(Theme.paper)
                        .disabled(env.purchases.uiState == .purchasing)
                        .accessibilityIdentifier("buy-button")
                    }
                    Button("Restore purchases") { Task { await env.purchases.restorePurchases() } }
                    if case .failed(let message) = env.purchases.uiState {
                        Text(message).font(.footnote).foregroundStyle(Theme.secondaryText)
                    }
                }
                .surfaceRows()
            }
            .noticeList()
            .navigationTitle("Unlock")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }

    private var buyTitle: String {
        if let product = env.purchases.product { return "Unlock for \(product.displayPrice)" }
        return "Unlock"
    }
}
