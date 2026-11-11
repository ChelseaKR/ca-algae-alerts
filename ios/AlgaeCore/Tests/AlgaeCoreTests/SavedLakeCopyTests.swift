import XCTest
@testable import AlgaeCore

/// A saved lake the data on this iPhone does not have (docs/DECISIONS.md
/// 0039). Its absence must never read as a fact about the state's file or
/// as "no advisory". Negative control: the old fixed line fails the same
/// checks, so they can tell the two apart.
final class SavedLakeCopyTests: XCTestCase {
    static let oldLine = "No longer in the state's current file."

    /// Problems with a line shown for a missing lake, given the date it must name.
    func problems(_ text: String, date: String?) -> [String] {
        var out: [String] = []
        if text.localizedCaseInsensitiveContains("state's current file") {
            out.append("claims the state's file dropped the lake")
        }
        if !text.contains(SavedLakeCopy.notAFinding) { out.append("no not-a-finding sentence") }
        if let date, !text.contains(date) { out.append("does not name the data's date \(date)") }
        out += affirmativeSafetyClaims(text).map { "safety claim: \($0)" }
        return out
    }

    func testTheOldLineFailsTheChecks() {
        XCTAssertFalse(problems(Self.oldLine, date: nil).isEmpty)
        XCTAssertFalse(problems(Self.oldLine, date: "Oct 12, 2026").isEmpty)
    }

    func testNoDataOnThePhoneSaysSoForEveryFavorite() {
        let text = SavedLakeCopy.detail(id: "ca-lake-elsinore", snapshot: nil)
        XCTAssertEqual(problems(text, date: nil), [])
        XCTAssertTrue(text.contains("no lake data on this iPhone"), text)
    }

    func testAMissingLakeNamesTheDataDate() throws {
        let snapshot = try Fixtures.multistate()
        XCTAssertNil(snapshot.waterbody(id: "ca-gone-lake"))  // the sabotage applies
        let text = SavedLakeCopy.detail(id: "ca-gone-lake", snapshot: snapshot)
        XCTAssertEqual(problems(text, date: snapshot.runDate.label), [])
        XCTAssertTrue(text.hasPrefix("This lake is not in Lake Notice's data dated"), text)
    }

    func testAStateWithNoLakesInTheDataIsNamed() throws {
        let traps = try Fixtures.traps()
        // The trap snapshot carries no Missouri water: a Missouri favorite
        // reads as Missouri missing from the data, not as the lake dropped.
        XCTAssertFalse(traps.waterbodies.contains { $0.state == "MO" })
        let text = SavedLakeCopy.detail(id: "mo-ashland-lake", snapshot: traps)
        XCTAssertEqual(problems(text, date: traps.runDate.label), [])
        XCTAssertTrue(text.contains("has no Missouri lakes"), text)

        // Negative control: with Missouri waters in the data, the same id is
        // just a missing lake.
        let multi = try Fixtures.multistate()
        XCTAssertTrue(multi.waterbodies.contains { $0.state == "MO" })
        let other = SavedLakeCopy.detail(id: "mo-gone-pond", snapshot: multi)
        XCTAssertFalse(other.contains("Missouri"), other)
    }

    func testAnUnknownPrefixGuessesNoState() {
        XCTAssertEqual(SavedLakeCopy.state(of: "mo-ashland-lake"), "MO")
        XCTAssertEqual(SavedLakeCopy.state(of: "ca-lake-elsinore"), "CA")
        XCTAssertNil(SavedLakeCopy.state(of: "ny-oneida-lake"))
        XCTAssertNil(SavedLakeCopy.state(of: ""))
    }
}
