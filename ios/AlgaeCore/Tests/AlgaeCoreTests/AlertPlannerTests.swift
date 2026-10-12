import XCTest
@testable import AlgaeCore

final class AlertPlannerTests: XCTestCase {
    let caution = Status(kind: .advisory, tier: .caution, level: "Caution", posted: PlainDate(year: 2026, month: 10, day: 9), sitesWithAdvisory: 1)
    let danger = Status(kind: .advisory, tier: .danger, level: "Danger", posted: PlainDate(year: 2026, month: 10, day: 9), sitesWithAdvisory: 1)
    let lifted = Status(kind: .noAdvisoryRecorded, liftKind: .noAdvisoryRecord, liftDate: PlainDate(year: 2026, month: 9, day: 1))

    func testFirstSightingOnlyRecords() throws {
        let s = try Fixtures.traps()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        let plan = AlertPlanner.plan(favorites: [alpha.id], snapshot: s, baseline: AlertBaseline())
        XCTAssertTrue(plan.notifications.isEmpty)
        XCTAssertEqual(plan.baseline.seen[alpha.id]?.kind, .advisory)
    }

    func testNewAdvisoryAfterARecordedEndAlerts() throws {
        let s = try Fixtures.traps()
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let first = AlertPlanner.plan(favorites: [beta.id], snapshot: s, baseline: AlertBaseline())
        let next = Fixtures.replacing(beta.id, status: caution, in: s)
        let plan = AlertPlanner.plan(favorites: [beta.id], snapshot: next, baseline: first.baseline)
        XCTAssertEqual(plan.notifications.count, 1)
        XCTAssertEqual(plan.notifications.first?.title, "Caution advisory: Beta Reservoir")
        XCTAssertTrue(plan.notifications[0].body.contains("Oct 9, 2026"))
        XCTAssertEqual(affirmativeSafetyClaims(plan.notifications[0].title + ". " + plan.notifications[0].body), [])
    }

    func testLevelChangeAlertsAndARepostDoesNot() throws {
        let s = try Fixtures.traps()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        let first = AlertPlanner.plan(favorites: [alpha.id], snapshot: s, baseline: AlertBaseline())
        let repost = Fixtures.replacing(alpha.id, status: caution, in: s)
        XCTAssertTrue(AlertPlanner.plan(favorites: [alpha.id], snapshot: repost, baseline: first.baseline).notifications.isEmpty)
        let raised = Fixtures.replacing(alpha.id, status: danger, in: s)
        let plan = AlertPlanner.plan(favorites: [alpha.id], snapshot: raised, baseline: first.baseline)
        XCTAssertEqual(plan.notifications.map(\.title), ["Lake Alpha: now a danger advisory"])
    }

    func testARecordedEndDoesNotAlertAndNonFavoritesNeverAlert() throws {
        let s = try Fixtures.traps()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        let first = AlertPlanner.plan(favorites: [alpha.id], snapshot: s, baseline: AlertBaseline())
        let ended = Fixtures.replacing(alpha.id, status: lifted, in: s)
        XCTAssertTrue(AlertPlanner.plan(favorites: [alpha.id], snapshot: ended, baseline: first.baseline).notifications.isEmpty)
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let other = Fixtures.replacing(beta.id, status: danger, in: s)
        XCTAssertTrue(AlertPlanner.plan(favorites: [alpha.id], snapshot: other, baseline: first.baseline).notifications.isEmpty)
    }

    func testAFavoriteMissingFromTheSnapshotKeepsItsBaseline() throws {
        let s = try Fixtures.traps()
        let baseline = AlertBaseline(seen: ["ca-gone-lake": .init(caution)])
        let plan = AlertPlanner.plan(favorites: ["ca-gone-lake"], snapshot: s, baseline: baseline)
        XCTAssertEqual(plan.baseline.seen["ca-gone-lake"], .init(caution))
    }

    func testMutesFilterAlertsButNotTheBaseline() throws {
        let s = try Fixtures.traps()
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        let first = AlertPlanner.plan(favorites: [beta.id], snapshot: s, baseline: AlertBaseline())
        let plan = AlertPlanner.plan(favorites: [beta.id], snapshot: Fixtures.replacing(beta.id, status: caution, in: s), baseline: first.baseline)
        var muted = MutedWaters()
        muted.mute(beta.id)
        XCTAssertTrue(muted.unmuted(plan.notifications).isEmpty)
        XCTAssertEqual(plan.baseline.seen[beta.id]?.kind, .advisory)
        muted.unmute(beta.id)
        XCTAssertEqual(muted.unmuted(plan.notifications).count, 1)
    }

    func testOnlyAPurchaseAllowsAlertsAndTheWidget() {
        XCTAssertFalse(FreeTier.notificationsAllowed(isEntitled: false))
        XCTAssertTrue(FreeTier.notificationsAllowed(isEntitled: true))
        XCTAssertFalse(FreeTier.widgetUnlocked(isEntitled: false))
        XCTAssertTrue(FreeTier.widgetUnlocked(isEntitled: true))
    }
}
