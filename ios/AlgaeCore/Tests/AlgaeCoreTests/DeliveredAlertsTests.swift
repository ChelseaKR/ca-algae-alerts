import XCTest
@testable import AlgaeCore

/// The same alert is never delivered twice (DECISIONS 0031): not after a
/// relaunch, and not when a later snapshot drops an advisory and the next
/// one brings it back.
final class DeliveredAlertsTests: XCTestCase {
    let caution = Status(kind: .advisory, tier: .caution, level: "Caution", posted: PlainDate(year: 2026, month: 10, day: 9), sitesWithAdvisory: 1)
    let danger = Status(kind: .advisory, tier: .danger, level: "Danger", posted: PlainDate(year: 2026, month: 10, day: 9), sitesWithAdvisory: 1)
    let repostedLater = Status(kind: .advisory, tier: .caution, level: "Caution", posted: PlainDate(year: 2026, month: 11, day: 2), sitesWithAdvisory: 1)
    let lifted = Status(kind: .noAdvisoryRecorded, liftKind: .noAdvisoryRecord, liftDate: PlainDate(year: 2026, month: 9, day: 1))

    /// What the app does on each new snapshot: plan, drop what was already
    /// delivered, record the rest, and save both files.
    func deliver(_ snapshot: Snapshot, favorites: Set<Waterbody.ID>, stores: AppStores) throws -> [PlannedNotification] {
        let plan = AlertPlanner.plan(favorites: favorites, snapshot: snapshot, baseline: stores.baseline())
        try stores.save(plan.baseline)
        var delivered = stores.delivered()
        let fresh = delivered.undelivered(plan.notifications)
        for n in fresh { delivered.record(n.id) }
        try stores.save(delivered)
        return fresh
    }

    func testAnAdvisoryThatDropsOutAndReturnsDoesNotAlertAgain() throws {
        let s = try Fixtures.traps()
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let stores = AppStores(layout: try Fixtures.tempLayout())
        XCTAssertEqual(try deliver(s, favorites: [beta.id], stores: stores), [])
        let posted = Fixtures.replacing(beta.id, status: caution, in: s)
        XCTAssertEqual(try deliver(posted, favorites: [beta.id], stores: stores).map(\.title), ["Caution advisory: Beta Reservoir"])
        // A short or broken file drops it, then the next file brings it back.
        let dropped = Fixtures.replacing(beta.id, status: lifted, in: s)
        XCTAssertEqual(try deliver(dropped, favorites: [beta.id], stores: stores), [])
        // The planner alone would announce it again; the delivered keys stop it.
        let planned = AlertPlanner.plan(favorites: [beta.id], snapshot: posted, baseline: stores.baseline())
        XCTAssertEqual(planned.notifications.count, 1)
        XCTAssertEqual(try deliver(posted, favorites: [beta.id], stores: stores), [])
    }

    func testDeliveredKeysSurviveARelaunch() throws {
        let s = try Fixtures.traps()
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let layout = try Fixtures.tempLayout()
        let first = AppStores(layout: layout)
        _ = try deliver(s, favorites: [beta.id], stores: first)
        let posted = Fixtures.replacing(beta.id, status: caution, in: s)
        let sent = try deliver(posted, favorites: [beta.id], stores: first)
        XCTAssertEqual(sent.count, 1)
        // A new process: nothing in memory, only the files on disk. Even with
        // the baseline lost, the delivered file holds the key.
        let relaunched = AppStores(layout: layout)
        XCTAssertTrue(relaunched.delivered().contains(sent[0].id))
        try FileManager.default.removeItem(at: layout.baselineFile)
        let withStaleBaseline = AlertBaseline(seen: [beta.id: .init(lifted)])
        try relaunched.save(withStaleBaseline)
        XCTAssertEqual(try deliver(posted, favorites: [beta.id], stores: relaunched), [])
    }

    func testANewLevelOrANewPostingStillAlerts() throws {
        let s = try Fixtures.traps()
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let stores = AppStores(layout: try Fixtures.tempLayout())
        _ = try deliver(s, favorites: [beta.id], stores: stores)
        _ = try deliver(Fixtures.replacing(beta.id, status: caution, in: s), favorites: [beta.id], stores: stores)
        XCTAssertEqual(try deliver(Fixtures.replacing(beta.id, status: danger, in: s), favorites: [beta.id], stores: stores).map(\.title),
                       ["Beta Reservoir: now a danger advisory"])
        _ = try deliver(Fixtures.replacing(beta.id, status: lifted, in: s), favorites: [beta.id], stores: stores)
        XCTAssertEqual(try deliver(Fixtures.replacing(beta.id, status: repostedLater, in: s), favorites: [beta.id], stores: stores).count, 1)
    }

    func testOneKeyOnceEvenWithinOnePlan() {
        let n = PlannedNotification(id: "ca-x|caution|2026-10-09", waterID: "ca-x", title: "t", body: "b")
        XCTAssertEqual(DeliveredAlerts().undelivered([n, n]).count, 1)
        XCTAssertEqual(DeliveredAlerts(keys: [n.id]).undelivered([n]), [])
    }

    func testAMissingOrCorruptFileReadsAsEmpty() throws {
        let layout = try Fixtures.tempLayout()
        let stores = AppStores(layout: layout)
        XCTAssertEqual(stores.delivered(), DeliveredAlerts())
        try Data("not json".utf8).write(to: layout.deliveredFile)
        XCTAssertEqual(stores.delivered(), DeliveredAlerts())
    }
}
