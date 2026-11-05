import XCTest
@testable import AlgaeCore

/// The app says what the website says about a water's advisories
/// (docs/DECISIONS.md 0017). `Fixtures/elsinore-parity.json` is built by
/// `pipeline/tests/test_ios_parity_fixture.py` from Lake Elsinore's real
/// records (the state's file dated 2026-11-03): each case holds the
/// snapshot the pipeline builds and the website's sentences for it. The
/// pipeline test fails when the file is stale, so the two cannot drift.
final class AdvisoryParityTests: XCTestCase {
    struct Case {
        let name: String
        let snapshot: Snapshot
        let expected: [String: Any]

        var water: Waterbody { snapshot.waterbodies[0] }
        func text(_ key: String) -> String? { expected[key] as? String }
    }

    static func cases() throws -> [Case] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "elsinore-parity", withExtension: "json", subdirectory: "Fixtures"))
        let root = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let raw = try XCTUnwrap(root["cases"] as? [[String: Any]])
        return try raw.map { item in
            let data = try JSONSerialization.data(withJSONObject: try XCTUnwrap(item["snapshot"]))
            let snapshot = try SnapshotDecoder.decode(data)
            XCTAssertEqual(snapshot.waterbodies.count, 1)
            return Case(name: try XCTUnwrap(item["name"] as? String), snapshot: snapshot, expected: try XCTUnwrap(item["expected"] as? [String: Any]))
        }
    }

    func testEveryCaseSaysWhatTheWebsiteSays() throws {
        let cases = try Self.cases()
        XCTAssertEqual(cases.count, 6)
        for c in cases {
            let w = c.water
            XCTAssertEqual(StatusWording.headline(w.status), c.text("headline"), c.name)
            XCTAssertEqual(StatusWording.newerPosting(w), c.text("newer_posting"), c.name)
            XCTAssertEqual(StatusWording.olderHigher(w), c.text("older_higher"), c.name)
            XCTAssertEqual(StatusWording.ageNote(w, fileDate: c.snapshot.fileDate(for: w)), c.text("age_note"), c.name)
            XCTAssertEqual(WaterSearch.newestPosted(w)?.iso, c.text("newest_posted"), c.name)
            let recentOn = try XCTUnwrap(c.text("recent_on").flatMap(PlainDate.init(iso:)))
            XCTAssertEqual(WaterSearch.isRecent(w, today: recentOn), c.expected["is_recent_on"] as? Bool, c.name)
            XCTAssertEqual(WaterSearch.isRecent(w, today: c.snapshot.runDate), c.expected["is_recent_on_run_date"] as? Bool, c.name)
            XCTAssertEqual(w.status.sitesWithAdvisory, c.expected["sites_with_advisory"] as? Int, c.name)
            XCTAssertEqual(w.sites.map(\.id).sorted(), c.expected["site_ids"] as? [String], c.name)
        }
    }

    func testElsinoreLeadsWithTheCautionAndNamesTheOlderDanger() throws {
        let c = try XCTUnwrap(try Self.cases().first { $0.name == "elsinore" })
        let notes = StatusWording.statusNotes(c.water, fileDate: c.snapshot.fileDate(for: c.water))
        XCTAssertEqual(StatusWording.headline(c.water.status), "Caution advisory, last posted Sep 24, 2026. No all-clear recorded.")
        XCTAssertEqual(notes, ["An older, higher advisory is also on file: Danger advisory, last posted Sep 3, 2020 at 2 reported spots. No all-clear recorded."])
        // The None filed under report 3927 at report 3289's coordinates ends
        // the 2022 Danger there: one spot, named by the newer report.
        XCTAssertNil(c.water.site(id: "3289"))
        XCTAssertEqual(c.water.site(id: "3927")?.status.kind, .noAdvisoryRecorded)
    }

    func testNegativeControlLoweringTheOldDangersRemovesTheLine() throws {
        let c = try XCTUnwrap(try Self.cases().first { $0.name == "elsinore" })
        XCTAssertNotNil(StatusWording.olderHigher(c.water))
        let lowered = c.water.sites.map { site -> Site in
            guard site.status.tier == .danger else { return site }
            let s = site.status
            let caution = Status(kind: s.kind, tier: .caution, level: "Caution", posted: s.posted, plannedEnd: s.plannedEnd, liftKind: s.liftKind, liftDate: s.liftDate, lastAdvisory: s.lastAdvisory, sitesWithAdvisory: s.sitesWithAdvisory)
            return Site(id: site.id, landmark: site.landmark, lat: site.lat, lon: site.lon, status: caution)
        }
        XCTAssertTrue(zip(lowered, c.water.sites).contains { $0.status != $1.status }) // it applied
        XCTAssertNil(StatusWording.olderHigher(replacingSites(c.water, lowered)))
    }

    func testNegativeControlTheAgeLineNeedsTheFileDateAndAnOldPosting() throws {
        let c = try XCTUnwrap(try Self.cases().first { $0.name == "history_only" })
        XCTAssertNotNil(StatusWording.ageNote(c.water, fileDate: c.snapshot.fileDate(for: c.water)))
        XCTAssertNil(StatusWording.ageNote(c.water, fileDate: nil))
        // 90 days after the posting is not stale; 91 is.
        let posted = try XCTUnwrap(c.water.status.posted)
        XCTAssertNil(StatusWording.ageNote(c.water, fileDate: PlainDate(year: 2021, month: 10, day: 17)))
        XCTAssertEqual(posted.days(until: PlainDate(year: 2021, month: 10, day: 17)), 90)
        XCTAssertNotNil(StatusWording.ageNote(c.water, fileDate: PlainDate(year: 2021, month: 10, day: 18)))
        XCTAssertEqual(StatusWording.age(days: 400), "more than a year")
        XCTAssertEqual(StatusWording.age(days: 100), "3 months")
        XCTAssertEqual(StatusWording.age(days: 1934), "more than 5 years")
    }

    func testANewerLowerPostingKeepsTheWaterOnTheRecentList() throws {
        let c = try XCTUnwrap(try Self.cases().first { $0.name == "newer_lower" })
        let oct1 = PlainDate(year: 2026, month: 10, day: 1)
        // The headline is the Danger posted Mar 10, 2026; a Caution was posted
        // Sep 24. The headline's own date alone would hide it.
        XCTAssertFalse(WaterSearch.isRecent(c.water.status, today: oct1))
        XCTAssertTrue(WaterSearch.isRecent(c.water, today: oct1))
        let older = try XCTUnwrap(try Self.cases().first { $0.name == "history_only" })
        let renamed = Waterbody(id: "b", state: "CA", name: "A water", countyText: "", counties: [], center: nil, status: older.water.status, sites: older.water.sites, records: older.water.records)
        XCTAssertEqual(WaterSearch.advisories([renamed, c.water]).map(\.id), [c.water.id, "b"])
    }

    func testNoNoteClaimsSafety() throws {
        for c in try Self.cases() {
            let lines = StatusWording.statusNotes(c.water, fileDate: c.snapshot.fileDate(for: c.water)) + [StatusWording.headlineRule]
            for line in lines { XCTAssertEqual(affirmativeSafetyClaims(line), [], line) }
        }
    }

    private func replacingSites(_ w: Waterbody, _ sites: [Site]) -> Waterbody {
        Waterbody(id: w.id, state: w.state, name: w.name, countyText: w.countyText, counties: w.counties, center: w.center, status: w.status, sites: sites, records: w.records, satellite: w.satellite)
    }
}
