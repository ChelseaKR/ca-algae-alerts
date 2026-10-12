import XCTest
import StoreKit
import UIKit
@testable import AlgaeAlerts
import AlgaeCore

@MainActor
final class AppTests: XCTestCase {
    func layout() throws -> AppStorageLayout {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return AppStorageLayout(directory: dir)
    }

    func testBundledSnapshotLoadsAndIsTheStatesData() throws {
        let env = AppEnvironment(layout: try layout(), launch: .init())
        let snapshot = try XCTUnwrap(env.snapshot)
        XCTAssertGreaterThan(snapshot.waterbodies.count, 800)
        XCTAssertEqual(snapshot.sources.first?.state, "CA")
    }

    func testFavoriteSetsTheBaselineWithoutAlerting() async throws {
        let l = try layout()
        let env = AppEnvironment(layout: l, launch: .init())
        let water = try XCTUnwrap(env.snapshot?.waterbodies.first { $0.status.kind == .advisory })
        env.toggleFavorite(water.id)
        XCTAssertTrue(env.isFavorite(water.id))
        await env.planAlerts(schedule: false)
        XCTAssertEqual(AppStores(layout: l).baseline().seen[water.id]?.kind, .advisory)
        env.toggleFavorite(water.id)
        XCTAssertFalse(env.isFavorite(water.id))
    }

    func testMuteRoundTrips() throws {
        let l = try layout()
        let env = AppEnvironment(layout: l, launch: .init())
        env.setMuted("ca-x", true)
        XCTAssertTrue(AppStores(layout: l).muted().contains("ca-x"))
        env.setMuted("ca-x", false)
        XCTAssertFalse(env.isMuted("ca-x"))
    }

    func testIntroIsShownOnceAndCanBeShownAgain() throws {
        let l = try layout()
        let env = AppEnvironment(layout: l, launch: .init())
        XCTAssertFalse(env.introSeen)
        env.finishIntro()
        XCTAssertTrue(AppEnvironment(layout: l, launch: .init()).introSeen)
        env.showIntroAgain()
        XCTAssertFalse(env.introSeen)
    }

    func testRouterOpensLakesAndTheUnlock() {
        let router = AppRouter()
        router.handle(URL(string: "algaealerts://water/ca-alameda-lake-temescal")!)
        XCTAssertEqual(router.openWater, "ca-alameda-lake-temescal")
        XCTAssertEqual(router.tab, .advisories)
        router.handle(WaterLink.unlockURL)
        XCTAssertTrue(router.showUnlock)
    }

    func testCancelledAndPendingPurchasesAreNotFailures() {
        XCTAssertEqual(PurchaseManager.nextUIState(forNonSuccess: .userCancelled), .idle)
        XCTAssertEqual(PurchaseManager.nextUIState(forNonSuccess: .pending), .idle)
        XCTAssertEqual(PurchaseManager.productID, "net.chelseakr.algaealerts.fullaccess")
    }

    func testEntitlementPersistsAndUnlocksTheWidgetDigest() throws {
        let l = try layout()
        let env = AppEnvironment(layout: l, launch: .init())
        env.purchases.setEntitled(true)
        XCTAssertTrue(EntitlementStore(layout: l).load().isPurchased)
        let digest = WidgetDigest.build(snapshot: env.snapshot, favorites: env.favorites, isEntitled: env.isEntitled, lastCheckFailed: false)
        XCTAssertFalse(digest.locked)
        env.purchases.setEntitled(false)
    }

    /// The amber and teal against the backgrounds they sit on, in both
    /// appearances: WCAG AA for body text (4.5:1).
    func testThemeContrast() {
        func lum(_ c: UIColor) -> CGFloat {
            var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
            c.getRed(&r, green: &g, blue: &b, alpha: &a)
            func ch(_ x: CGFloat) -> CGFloat { x <= 0.03928 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
            return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
        }
        func ratio(_ a: UIColor, _ b: UIColor) -> CGFloat {
            let (x, y) = (lum(a), lum(b))
            return (max(x, y) + 0.05) / (min(x, y) + 0.05)
        }
        for style in [UIUserInterfaceStyle.light, .dark] {
            let traits = UITraitCollection(userInterfaceStyle: style)
            for color in [UIColor(Theme.advisory), UIColor(Theme.accent), UIColor(Theme.secondaryText), UIColor(Theme.label)] {
                let fg = color.resolvedColor(with: traits)
                for bg in [UIColor.systemBackground, .secondarySystemBackground, .systemGroupedBackground, .secondarySystemGroupedBackground] {
                    XCTAssertGreaterThanOrEqual(ratio(fg, bg.resolvedColor(with: traits)), 4.5, "\(style.rawValue)")
                }
            }
        }
    }
}
