import SwiftUI
import StoreKit
import AlgaeCore

struct LakeDetailView: View {
    @Environment(AppEnvironment.self) private var env
    @Environment(AppRouter.self) private var router
    @Environment(\.requestReview) private var requestReview
    let id: Waterbody.ID
    /// Set when the person saves this lake on this visit; leaving the screen
    /// afterward is the one moment the app may ask for a rating (0036).
    @State private var savedHere = false

    var body: some View {
        if let water = env.snapshot?.waterbody(id: id) {
            content(water)
        } else {
            NoticeEmptyState(board: NoticeBoard(title: EmptyCopy.goneTitle, message: EmptyCopy.goneMessage, systemImage: "doc.questionmark"))
        }
    }

    private func content(_ water: Waterbody) -> some View {
        List {
            if let outage = water.status.unavailable {
                // The state's data is unavailable (DECISIONS 0024): the
                // notice leads, and nothing below claims a current status.
                Section {
                    Text(StatusWording.unavailableBanner(outage)).font(.headline)
                    if let map = URL(string: outage.mapUrl) {
                        Link("\(outage.stateName) state map", destination: map)
                    }
                }
                .accessibilityIdentifier("state-unavailable")
            }
            Section {
                // The name, in full and wrapped: a large navigation title
                // truncates a long name, so the bar shows it small and the
                // content shows it large.
                Text(water.name)
                    .font(.signage(.largeTitle, weight: .heavy))
                    .foregroundStyle(Theme.ink)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("lake-name")
                    .listRowBackground(Theme.paper)
                NoticeCard(band: NoticeBand(water.status)) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(StatusWording.headline(water.status)).font(.headline).foregroundStyle(Theme.ink)
                    ForEach(StatusWording.statusNotes(water, fileDate: env.snapshot?.fileDate(for: water)), id: \.self) { note in
                        Text(note)
                    }
                    if water.status.kind == .noAdvisoryRecorded, let last = water.status.lastAdvisory {
                        Text("Last advisory on file: \(last.label).")
                    }
                    if water.status.kind == .advisory, let end = water.status.plannedEnd {
                        Text("The state set an end date of \(end.label).")
                    }
                    if water.status.sitesWithAdvisory > 1 {
                        Text("\(water.status.sitesWithAdvisory) reported spots here have an advisory with no all-clear recorded.")
                        Text(StatusWording.headlineRule).font(.footnote).foregroundStyle(Theme.secondaryText)
                    }
                    Text(StatusWording.caveat(water.status)).font(.footnote).foregroundStyle(Theme.secondaryText)
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("lake-status")
                }
                // Inset from the section's rounded corners, which would
                // otherwise clip the notice's edge.
                .padding(.horizontal, 8)
                .padding(.top, 4)
                .padding(.bottom, 18)
                .listRowInsets(EdgeInsets())
                .listRowBackground(Theme.paper)
            } header: {
                SectionTitle(water.countyLabel)
            }

            if let guidance = StatusWording.guidance(for: water) {
                Section {
                    Text(guidance)
                } header: { SectionTitle("What this level asks") }
                .surfaceRows()
            }

            Section {
                Text(StatusWording.humanAdvice)
                Text(StatusWording.notMedicalAdvice).font(.footnote).foregroundStyle(Theme.secondaryText)
            } header: { SectionTitle("After contact with the water") }
            .surfaceRows()

            Section {
                Text(StatusWording.dogAnswer(name: water.name, status: water.status))
                DisclosureGroup("Why dogs are more exposed") {
                    Text(StatusWording.dogAdvice).font(.callout)
                }
            } header: {
                SectionTitle("Dogs", systemImage: "pawprint")
            }
            .surfaceRows()

            alertsSection(water)

            if let satellite = water.satellite {
                SatelliteSection(satellite: satellite, attribution: env.snapshot?.source(id: satellite.source)?.attribution ?? "")
            }

            Section {
                ForEach(water.sites) { site in
                    VStack(alignment: .leading, spacing: 4) {
                        SignChip(band: NoticeBand(site.status))
                        Text(site.landmark.isEmpty ? "Spot not described" : site.landmark)
                        Text(StatusWording.headline(site.status)).font(.subheadline).foregroundStyle(Theme.secondaryText)
                    }
                    .accessibilityElement(children: .combine)
                }
            } header: { SectionTitle("Reported spots") }
            .surfaceRows()

            Section {
                ForEach(water.records) { record in
                    RecordRow(record: record, spot: water.site(id: record.site)?.landmark ?? "")
                }
            } header: {
                SectionTitle(water.status.unavailable.map(StatusWording.unavailableHistoryHeading) ?? "History")
            } footer: {
                Text("\"None\" is the state's record that no advisory was recommended that day. \"NA\" records change nothing.").foregroundStyle(Theme.label)
            }
            .surfaceRows()

            if let source = env.snapshot?.advisorySource(state: water.state) {
                Section {
                    Text(source.attribution).font(.footnote)
                    Text(source.liftExplanation).font(.footnote)
                    if !source.requiredDisclaimer.isEmpty {
                        Text(source.requiredDisclaimer).font(.caption2).accessibilityIdentifier("required-disclaimer")
                    }
                    Link("Official state algae page", destination: URL(string: source.officialMapUrl)!)
                    Link("This lake on the website", destination: LakeShare.url(for: water.id))
                } header: { SectionTitle("Source") }
                .surfaceRows()
            }
        }
        .noticeList()
        .navigationTitle(water.name)
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear {
            if env.takeReviewMoment(justSavedALake: savedHere && env.isFavorite(water.id)) { requestReview() }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                // The lake's page on the website: anyone can open it, no app
                // needed, and nothing about the sender goes with it.
                ShareLink(item: LakeShare.url(for: water.id),
                          subject: Text(LakeShare.subject(water)),
                          message: Text(LakeShare.message(water))) {
                    Image(systemName: "square.and.arrow.up")
                }
                .accessibilityLabel("Share \(water.name)")
                .accessibilityHint("Sends a link to this lake's page on lakenotice.com")
                .accessibilityIdentifier("share-lake")
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    env.toggleFavorite(water.id)
                    if env.isFavorite(water.id) { savedHere = true }
                } label: {
                    Image(systemName: env.isFavorite(water.id) ? "star.fill" : "star")
                }
                .accessibilityLabel(env.isFavorite(water.id) ? "Remove from favorites" : "Add to favorites")
                .accessibilityIdentifier("favorite-button")
            }
        }
    }

    @ViewBuilder
    private func alertsSection(_ water: Waterbody) -> some View {
        if env.isFavorite(water.id) {
            Section {
                if env.isEntitled {
                    Toggle("Alert me about new advisories here", isOn: Binding(
                        get: { !env.isMuted(water.id) },
                        set: { env.setMuted(water.id, !$0) }))
                } else {
                    Button("Unlock alerts and the widget") { router.showUnlock = true }
                }
            } header: { SectionTitle("Alerts") }
            .surfaceRows()
        }
    }
}

struct RecordRow: View {
    let record: AdvisoryRecord
    let spot: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            DateValueRow {
                Text(record.date.label).font(.subheadline.monospacedDigit())
            } trailing: {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    // The sign color as a swatch; the words carry the level.
                    let band = NoticeBand(record: record)
                    Rectangle()
                        .fill(Theme.band(band.paint))
                        .overlay(Rectangle().strokeBorder(Theme.ink, style: StrokeStyle(lineWidth: 1, dash: band.isAdvisory ? [] : [2, 2])))
                        .frame(width: 11, height: 11)
                        .accessibilityHidden(true)
                    Text(StatusWording.recordLevel(record))
                        .font(.subheadline.weight(record.tier.isAdvisory ? .bold : .regular))
                        .foregroundStyle(Theme.ink)
                }
            }
            if !spot.isEmpty { Text(spot).font(.footnote).foregroundStyle(Theme.secondaryText) }
            if let end = record.endDate { Text("End date recorded: \(end.label)").font(.footnote) }
            if let removed = record.removedFromSource { Text("Withdrawn from the state's file on \(removed.label)").font(.footnote) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// EPA CyAN's estimate, in its own clearly labeled section. Never an
/// advisory and never the end of one.
struct SatelliteSection: View {
    let satellite: SatelliteEstimate
    let attribution: String

    var body: some View {
        Section {
            if let latest = satellite.readings.first {
                Text("Week ending \(latest.weekEnd.label): \(StatusWording.cellsLabel(latest.cellsPerMl)) of cyanobacteria near the center of \(satellite.cyanName).")
                    .font(.headline)
                ForEach(satellite.readings.dropFirst(), id: \.weekEnd) { r in
                    DateValueRow {
                        Text(r.weekEnd.label).font(.subheadline.monospacedDigit())
                    } trailing: {
                        Text(StatusWording.cellsLabel(r.cellsPerMl)).font(.subheadline)
                    }
                    .accessibilityElement(children: .combine)
                }
            } else {
                Text("No satellite reading on file for \(satellite.cyanName) in recent weeks. Clouds, ice, or a lake shape the satellite's estimate near its center misses can cause this. It is a gap in the data, not a reading.")
            }
            Text(StatusWording.satelliteExplainer).font(.footnote)
            Text(attribution).font(.caption2).foregroundStyle(Theme.secondaryText)
        } header: {
            SectionTitle("Satellite estimate (not an advisory)", systemImage: "globe.americas")
        }
        .surfaceRows()
    }
}
