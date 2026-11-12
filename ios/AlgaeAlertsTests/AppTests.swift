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

    /// The identity's colors (docs/DESIGN.md, DECISIONS 0036) from the
    /// asset catalog, in both appearances: every text token on every
    /// background it sits on, and each sign band's ink on its band, at WCAG
    /// AA for body text (4.5:1).
    func testThemeContrast() throws {
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
        func named(_ name: String) throws -> UIColor {
            try XCTUnwrap(UIColor(named: name, in: Bundle(for: AppEnvironment.self), compatibleWith: nil), "no color \(name) in the asset catalog")
        }
        for style in [UIUserInterfaceStyle.light, .dark] {
            let traits = UITraitCollection(userInterfaceStyle: style)
            let text = try ["Ink", "Muted", "AccentColor", "Brand"].map { ($0, try named($0).resolvedColor(with: traits)) }
            let grounds = try ["Paper", "Surface"].map { ($0, try named($0).resolvedColor(with: traits)) }
            for (t, fg) in text {
                for (g, bg) in grounds {
                    XCTAssertGreaterThanOrEqual(ratio(fg, bg), 4.5, "\(t) on \(g), style \(style.rawValue)")
                }
            }
            for paint in NoticeBand.Paint.allCases {
                let band = try named(Theme.bandName(paint)).resolvedColor(with: traits)
                let ink = try named(Theme.bandInkName(paint)).resolvedColor(with: traits)
                XCTAssertGreaterThanOrEqual(ratio(ink, band), 4.5, "\(paint) band, style \(style.rawValue)")
            }
        }
    }

    /// No color in the identity is green: green reads as "go", and this app
    /// never says a water is safe.
    func testNoIdentityColorIsGreen() throws {
        let names = ["Paper", "Surface", "Ink", "Muted", "Brand", "Rule", "AccentColor"]
            + NoticeBand.Paint.allCases.flatMap { [Theme.bandName($0), Theme.bandInkName($0)] }
        for style in [UIUserInterfaceStyle.light, .dark] {
            for name in names {
                let c = try XCTUnwrap(UIColor(named: name, in: Bundle(for: AppEnvironment.self), compatibleWith: nil))
                    .resolvedColor(with: UITraitCollection(userInterfaceStyle: style))
                var h: CGFloat = 0, sat: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
                c.getHue(&h, saturation: &sat, brightness: &b, alpha: &a)
                let isGreen = sat > 0.2 && h > 75.0 / 360 && h < 165.0 / 360
                XCTAssertFalse(isGreen, "\(name) reads as green, style \(style.rawValue)")
            }
        }
    }

    func testTheReviewMomentNeverComesUnderUITests() throws {
        var launch = AppEnvironment.LaunchOptions()
        launch.uiTesting = true
        let env = AppEnvironment(layout: try layout(), launch: launch)
        XCTAssertFalse(env.takeReviewMoment(justSavedALake: true))
    }

    func testOpeningCountsDaysAndPersists() throws {
        let l = try layout()
        let env = AppEnvironment(layout: l, launch: .init())
        env.noteOpened(now: Date(timeIntervalSince1970: 1_780_000_000))
        env.noteOpened(now: Date(timeIntervalSince1970: 1_780_000_000 + 86_400 * 2))
        XCTAssertEqual(AppStores(layout: l).reviewAsk().daysOpened.count, 2)
    }
}
