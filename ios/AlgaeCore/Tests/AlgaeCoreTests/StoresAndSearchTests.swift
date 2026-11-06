import XCTest
@testable import AlgaeCore

final class StoresAndSearchTests: XCTestCase {
    func testStoresRoundTripAndDefaultToEmpty() throws {
        let stores = AppStores(layout: try Fixtures.tempLayout())
        XCTAssertEqual(stores.favorites(), Favorites())
        XCTAssertFalse(stores.entitlement().isPurchased)
        XCTAssertFalse(stores.intro().seen)
        var f = Favorites()
        f.toggle("ca-a")
        f.toggle("ca-b")
        f.toggle("ca-a")
        try stores.save(f)
        XCTAssertEqual(stores.favorites().ids, ["ca-b"])
        try stores.save(PurchaseEntitlement(isPurchased: true))
        XCTAssertTrue(stores.entitlement().isPurchased)
    }

    func testCorruptMuteFileReadsAsNothingMuted() throws {
        let layout = try Fixtures.tempLayout()
        try Data("not json".utf8).write(to: layout.mutedFile)
        XCTAssertEqual(AppStores(layout: layout).muted(), MutedWaters())
    }

    func testSnapshotStorePrefersTheNewerFile() throws {
        let layout = try Fixtures.tempLayout()
        let bundled = layout.directory.appendingPathComponent("bundled.json")
        try Fixtures.trapsData().write(to: bundled)
        let store = SnapshotStore(layout: layout, bundled: bundled)
        XCTAssertEqual(store.load()?.waterbodies.count, 9)
        XCTAssertNil(SnapshotStore(layout: layout, bundled: nil).load())
    }

    func testSearchAndOrdering() throws {
        let s = try Fixtures.traps()
        XCTAssertEqual(WaterSearch.filter(s.waterbodies, query: "alpha").map(\.name), ["Lake Alpha"])
        XCTAssertEqual(WaterSearch.filter(s.waterbodies, query: "tuolumne").map(\.name), ["Epsilon Creek"])
        XCTAssertEqual(WaterSearch.filter(s.waterbodies, query: " ").count, 9)
        let advisories = WaterSearch.advisories(s.waterbodies)
        XCTAssertEqual(advisories.first?.name, "Delta Lake")
        XCTAssertEqual(advisories.last?.name, "Zeta Lake")
        XCTAssertTrue(advisories.allSatisfy { $0.status.kind == .advisory })
        let today = PlainDate(year: 2026, month: 10, day: 12)
        XCTAssertTrue(WaterSearch.isRecent(advisories[0].status, today: today))
        XCTAssertFalse(WaterSearch.isRecent(advisories.last!.status, today: today))
    }

    func testWidgetDigestLockedAndUnlocked() throws {
        let s = try Fixtures.traps()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        let favorites = Favorites(ids: [alpha.id, "ca-gone"])
        let locked = WidgetDigest.build(snapshot: s, favorites: favorites, isEntitled: false, lastCheckFailed: false)
        XCTAssertTrue(locked.locked)
        XCTAssertTrue(locked.rows.isEmpty)
        XCTAssertEqual(locked.advisoryCount, 6)
        let open = WidgetDigest.build(snapshot: s, favorites: favorites, isEntitled: true, lastCheckFailed: true)
        XCTAssertFalse(open.locked)
        XCTAssertEqual(open.rows.map(\.name), ["Lake Alpha"])
        XCTAssertEqual(open.missingFavorites, 1)
        for row in open.rows {
            XCTAssertFalse(row.spokenLine.contains("·"), row.spokenLine)
            XCTAssertEqual(row.spokenLine, row.line.replacingOccurrences(of: " · ", with: ", "))
        }
        XCTAssertEqual(WidgetDigest.build(snapshot: nil, favorites: favorites, isEntitled: true, lastCheckFailed: false), .empty)
    }

    func testLinks() {
        XCTAssertEqual(WaterLink.destination(for: WaterLink.url(for: "ca-alameda-lake-alpha")), .water("ca-alameda-lake-alpha"))
        XCTAssertEqual(WaterLink.destination(for: WaterLink.unlockURL), .unlock)
        XCTAssertNil(WaterLink.destination(for: URL(string: "algaealerts://water/BAD%20ID")!))
        XCTAssertNil(WaterLink.destination(for: URL(string: "https://example.com/water/x")!))
    }

    func testThrottle() {
        let now = Date()
        XCTAssertTrue(RefreshThrottle.isDue(SnapshotMeta(), now: now))
        XCTAssertFalse(RefreshThrottle.isDue(SnapshotMeta(lastAttempt: now.addingTimeInterval(-3600)), now: now))
        XCTAssertTrue(RefreshThrottle.isDue(SnapshotMeta(lastAttempt: now.addingTimeInterval(-3600), lastAttemptFailed: true), now: now))
    }
}
