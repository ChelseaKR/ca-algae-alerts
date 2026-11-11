import XCTest
@testable import AlgaeCore

/// A state in its "data unavailable" mode (docs/DECISIONS.md 0024): the app
/// shows no status for its waters, lists none of them as advisories, and
/// sends no alert, and its return announces only a real change. Each test
/// has its negative control: the same snapshot with the state live.
final class UnavailableStateTests: XCTestCase {
    static let entry: [String: Any] = [
        "state": "MO", "source": "mo-dnr-hab", "mode": "unavailable",
        "last_read": "2026-10-11", "since": "2026-10-12",
        "reason": "superseded: the viewer moved",
        "map_url": "https://dnr.mo.gov/water/alerts-hazards/harmful-algal-bloom-hab-reports-map",
    ]

    func snapshot(_ entries: [[String: Any]]?) throws -> Snapshot {
        var object = try XCTUnwrap(JSONSerialization.jsonObject(with: Fixtures.multistateData()) as? [String: Any])
        object["state_status"] = entries
        return try SnapshotDecoder.decode(JSONSerialization.data(withJSONObject: object))
    }

    func moAdvisoryID(_ s: Snapshot) throws -> Waterbody.ID {
        try XCTUnwrap(s.waterbodies.first { $0.state == "MO" && $0.status.kind == .advisory }).id
    }

    func testAnUnavailableStateShowsNoStatusAnywhere() throws {
        let live = try snapshot(nil)
        let id = try moAdvisoryID(live)  // negative control: an advisory when live
        let down = try snapshot([Self.entry])
        let water = try XCTUnwrap(down.waterbody(id: id))
        XCTAssertEqual(water.status.kind, .undetermined)
        let outage = try XCTUnwrap(water.status.unavailable)
        XCTAssertEqual(StatusWording.headline(water.status), "No current status: Missouri's data unavailable since Oct 12, 2026.")
        XCTAssertEqual(StatusWording.unavailableBanner(outage), "Missouri's harmful algal bloom data stopped reaching Lake Notice on Oct 12, 2026, so Lake Notice can't show this water's current status. The records below are the last ones it read, on Oct 11, 2026.")
        XCTAssertEqual(StatusWording.unavailableHistoryHeading(outage), "Records read before Oct 12, 2026")
        for line in [StatusWording.headline(water.status), StatusWording.shortLine(water.status),
                     StatusWording.caveat(water.status), StatusWording.dogAnswer(name: water.name, status: water.status)] {
            XCTAssertFalse(line.contains("No all-clear recorded"), line)
            XCTAssertFalse(line.contains("recommends no advisory"), line)
            XCTAssertFalse(line.contains("No advisory"), line)
            XCTAssertEqual(affirmativeSafetyClaims(line), [], line)
        }
        XCTAssertTrue(water.sites.allSatisfy { $0.status.unavailable != nil })
        XCTAssertNil(StatusWording.guidance(for: water))
        // The records themselves are kept, as history.
        XCTAssertEqual(water.records, try XCTUnwrap(live.waterbody(id: id)).records)
        // California is untouched.
        let ca = down.waterbodies.filter { $0.state == "CA" }
        XCTAssertEqual(ca, live.waterbodies.filter { $0.state == "CA" })
        XCTAssertFalse(WaterSearch.advisories(down.waterbodies).contains { $0.state == "MO" })
        XCTAssertTrue(WaterSearch.advisories(live.waterbodies).contains { $0.state == "MO" })
    }

    func testNoAlertWhileUnavailableAndNoReAlertOnReturn() throws {
        let live = try snapshot(nil)
        let id = try moAdvisoryID(live)
        let first = AlertPlanner.plan(favorites: [id], snapshot: live, baseline: AlertBaseline())
        let down = try snapshot([Self.entry])
        let during = AlertPlanner.plan(favorites: [id], snapshot: down, baseline: first.baseline)
        XCTAssertEqual(during.notifications, [])
        XCTAssertEqual(during.baseline, first.baseline)  // kept, not overwritten
        let back = AlertPlanner.plan(favorites: [id], snapshot: live, baseline: during.baseline)
        XCTAssertEqual(back.notifications, [])
        // Negative control: had the baseline been overwritten with the
        // masked status, the return would alert again.
        let overwritten = AlertBaseline(seen: [id: AlertBaseline.Seen(try XCTUnwrap(down.waterbody(id: id)).status)])
        XCTAssertEqual(AlertPlanner.plan(favorites: [id], snapshot: live, baseline: overwritten).notifications.count, 1)
    }

    func testTheWidgetCountsNoUnavailableAdvisory() throws {
        let favorites = Favorites(ids: [])
        let live = WidgetDigest.build(snapshot: try snapshot(nil), favorites: favorites, isEntitled: false, lastCheckFailed: false)
        let down = WidgetDigest.build(snapshot: try snapshot([Self.entry]), favorites: favorites, isEntitled: false, lastCheckFailed: false)
        XCTAssertLessThan(down.advisoryCount, live.advisoryCount)
    }

    func testALiveOrStaleEntryChangesNothing() throws {
        var stale = Self.entry
        stale["mode"] = "stale_dated"
        stale["since"] = NSNull()
        stale["reason"] = NSNull()
        XCTAssertEqual(try snapshot([stale]).waterbodies, try snapshot(nil).waterbodies)
    }

    func testTheDecoderRefusesAnUnavailableStateWithoutItsDateOrAnUnknownMode() throws {
        var undated = Self.entry
        undated["since"] = NSNull()
        XCTAssertThrowsError(try snapshot([undated]))
        var unknown = Self.entry
        unknown["mode"] = "paused"
        XCTAssertThrowsError(try snapshot([unknown]))
    }
}
