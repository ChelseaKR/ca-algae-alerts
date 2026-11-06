import SwiftUI
import AlgaeCore

/// The first tab: current advisories first, each with its posted date, or
/// every lake on record. Search covers both.
struct AdvisoriesView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router
    @State private var query = ""
    @State private var scope: Scope = .advisories
    @State private var path: [Waterbody.ID] = []

    enum Scope: String, CaseIterable, Identifiable {
        case advisories = "Advisories"
        case all = "All lakes"
        var id: String { rawValue }
    }

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                if let snapshot = env.snapshot {
                    list(snapshot)
                } else {
                    ContentUnavailableView("No data yet", systemImage: "drop", description: Text("Pull to refresh to load the state's advisory records."))
                }
            }
            .navigationTitle("Algae advisories")
            .navigationDestination(for: Waterbody.ID.self) { id in LakeDetailView(id: id) }
            .searchable(text: $query, prompt: "Lake, river or county")
            .refreshable { await env.refreshNow() }
        }
        .onChange(of: router.openWater) { _, id in
            if let id { path = [id]; router.openWater = nil }
        }
        .onAppear {
            if let id = router.openWater { path = [id]; router.openWater = nil }
        }
    }

    @ViewBuilder
    private func list(_ snapshot: Snapshot) -> some View {
        let matches = WaterSearch.filter(snapshot.waterbodies, query: query)
        List {
            Section {
                Picker("Show", selection: $scope) {
                    ForEach(Scope.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                DataFreshnessView(snapshot: snapshot)
            }
            switch scope {
            case .advisories:
                let advisories = WaterSearch.advisories(matches)
                // Counted back from the data's run date, not this iPhone's
                // today, so an old copy never reads as a quiet month.
                let recent = advisories.filter { CoverageCopy.isRecent($0, in: snapshot) }
                let older = advisories.filter { !CoverageCopy.isRecent($0, in: snapshot) }
                Section {
                    if recent.isEmpty { Text(CoverageCopy.recentEmpty(snapshot)).foregroundStyle(Theme.secondaryText) }
                    ForEach(recent) { row($0) }
                } header: {
                    SectionTitle(CoverageCopy.recentHeader(snapshot))
                }
                Section {
                    ForEach(older) { row($0) }
                } header: {
                    SectionTitle("Older, no all-clear recorded")
                } footer: {
                    Text("The state never recorded an end for these, so they stay listed with their date. Reporting is voluntary.").foregroundStyle(Theme.label)
                }
            case .all:
                Section {
                    ForEach(WaterSearch.alphabetical(matches)) { row($0) }
                } footer: {
                    Text(CoverageCopy.allFooter(snapshot)).foregroundStyle(Theme.label)
                }
            }
        }
        .listStyle(.insetGrouped)
    }

    private func row(_ water: Waterbody) -> some View {
        NavigationLink(value: water.id) {
            LakeRow(water: water, isFavorite: env.isFavorite(water.id))
        }
    }
}

struct DataFreshnessView: View {
    @Environment(AppEnvironment.self) private var env
    let snapshot: Snapshot

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("California data file dated \(snapshot.sourceFile.fileDate.label)")
                .font(.footnote)
            if let mo = snapshot.sourceFiles.first(where: { $0.source == "mo-dnr-hab" }) {
                Text("Missouri data read \(mo.fileDate.label)").font(.footnote)
            }
            if env.lastCheckFailed {
                Text("The last check for newer data did not finish. Showing the copy on this iPhone.")
                    .font(.footnote).foregroundStyle(Theme.secondaryText)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
