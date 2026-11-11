import XCTest
@testable import AlgaeCore

/// Words built from the snapshot (DECISIONS 0031): the states named are the
/// ones with waters in the file, and "the last 30 days" counts back from the
/// file's run date, never from this device's today.
final class CoverageCopyTests: XCTestCase {
    /// The trap snapshot, run 2026-10-12, read on a much later day.
    let muchLater = PlainDate(year: 2027, month: 1, day: 20)

    func testRecentIsMeasuredFromTheRunDateOfAStaleSnapshot() throws {
        let s = try Fixtures.traps()
        XCTAssertEqual(s.runDate, PlainDate(year: 2026, month: 10, day: 12))
        let advisories = WaterSearch.advisories(s.waterbodies)
        let recent = advisories.filter { CoverageCopy.isRecent($0, in: s) }.map(\.name)
        // Posted 09-20 and 09-25: within 30 days of the run date.
        XCTAssertTrue(recent.contains("Lake Alpha"))
        XCTAssertTrue(recent.contains("Delta Lake"))
        XCTAssertFalse(recent.contains("Gamma Pond"))
        XCTAssertFalse(recent.contains("Zeta Lake"))
        // Measured from a device's later today, the same file would claim a
        // quiet month: that is the bug this guards.
        XCTAssertTrue(advisories.filter { WaterSearch.isRecent($0, today: muchLater) }.isEmpty)
    }

    func testTheListWordsNameTheRunDateNotToday() throws {
        let s = try Fixtures.traps()
        XCTAssertEqual(CoverageCopy.recentHeader(s), "Posted in the 30 days to Oct 12, 2026")
        XCTAssertEqual(CoverageCopy.recentEmpty(s), "None posted in the 30 days to Oct 12, 2026, the date of the data on this iPhone.")
        let footer = CoverageCopy.allFooter(s)
        XCTAssertTrue(footer.hasPrefix("As of the data dated Oct 12, 2026,"))
        XCTAssertTrue(footer.contains("no advisory record Lake Notice could read"))
        XCTAssertFalse(footer.contains("no advisory records at all"))
        for text in [CoverageCopy.recentHeader(s), CoverageCopy.recentEmpty(s), footer] {
            XCTAssertFalse(text.contains("last 30 days"), text)
            XCTAssertEqual(affirmativeSafetyClaims(text), [], text)
        }
    }

    func testAStateWithASourceButNoWatersIsNotNamed() throws {
        // The trap file lists Missouri's source but carries no Missouri water.
        let s = try Fixtures.traps()
        XCTAssertNotNil(s.advisorySource(state: "MO"))
        XCTAssertEqual(CoverageCopy.states(in: s).map(\.code), ["CA"])
        let about = CoverageCopy.aboutSummary(s)
        XCTAssertEqual(about, "Harmful algal bloom advisories that California has recorded for lakes, rivers and shorelines, with each water's history: California's since 2019.")
        XCTAssertFalse(about.contains("Missouri"))
        XCTAssertFalse(CoverageCopy.introSummary(s).contains("Missouri"))
        XCTAssertTrue(CoverageCopy.introSummary(s).hasPrefix("California advisories"))
    }

    func testBothStatesWhenBothHaveWatersWithTheirOwnFirstYears() throws {
        let s = try Fixtures.multistate()
        XCTAssertEqual(CoverageCopy.states(in: s), [
            StateCoverage(code: "CA", name: "California", firstRecordYear: 2019),
            StateCoverage(code: "MO", name: "Missouri", firstRecordYear: 2017),
        ])
        XCTAssertEqual(CoverageCopy.aboutSummary(s), "Harmful algal bloom advisories that California and Missouri have recorded for lakes, rivers and shorelines, with each water's history: California's since 2019 and Missouri's since 2017.")
        XCTAssertTrue(CoverageCopy.introSummary(s).hasPrefix("California and Missouri advisories"))
    }

    func testAStateWithNoDatedRecordGetsNoYear() throws {
        let s = try Fixtures.traps()
        let bare = s.waterbodies.map { w in
            Waterbody(id: w.id, state: w.state, name: w.name, countyText: w.countyText, counties: w.counties, center: w.center, status: w.status, sites: w.sites, records: [], satellite: w.satellite)
        }
        let noRecords = Snapshot(schemaVersion: 1, generatedAt: s.generatedAt, runDate: s.runDate, sources: s.sources, sourceFile: s.sourceFile, sourceFiles: s.sourceFiles, waterbodies: bare)
        XCTAssertEqual(CoverageCopy.states(in: noRecords), [StateCoverage(code: "CA", name: "California", firstRecordYear: nil)])
        let about = CoverageCopy.aboutSummary(noRecords)
        XCTAssertFalse(about.contains("since"), about)
        XCTAssertFalse(about.contains("0"), about)
    }

    func testNoSnapshotNamesNoState() {
        XCTAssertEqual(CoverageCopy.states(in: nil), [])
        XCTAssertFalse(CoverageCopy.aboutSummary(nil).contains("California"))
        XCTAssertTrue(CoverageCopy.introSummary(nil).hasPrefix("State advisories"))
    }

    func testJoined() {
        XCTAssertEqual(CoverageCopy.joined([]), "")
        XCTAssertEqual(CoverageCopy.joined(["California"]), "California")
        XCTAssertEqual(CoverageCopy.joined(["A", "B", "C"]), "A, B and C")
    }
}
