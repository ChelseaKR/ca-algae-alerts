import XCTest

/// Drives the real app on the simulator. `-uiTesting` keeps every file in a
/// fresh temporary folder and makes no network request.
final class AppUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    func launch(_ extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTesting"] + extra
        app.launch()
        return app
    }

    func testIntroThenBrowseOpenALakeAndFavoriteIt() {
        let app = launch()
        let start = app.buttons["start-browsing"]
        XCTAssertTrue(start.waitForExistence(timeout: 10))
        start.tap()
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Posted in the last 30 days"].exists || app.staticTexts["POSTED IN THE LAST 30 DAYS"].exists)
        app.searchFields.firstMatch.tap()
        app.searchFields.firstMatch.typeText("Temescal")
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Lake Temescal'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.otherElements["lake-status"].waitForExistence(timeout: 5) || app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'last posted'")).firstMatch.exists)
        let star = app.buttons["favorite-button"]
        XCTAssertEqual(star.label, "Add to favorites")
        star.tap()
        XCTAssertEqual(star.label, "Remove from favorites")
        app.tabBars.buttons["Favorites"].tap()
        XCTAssertTrue(app.staticTexts["Lake Temescal"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["open-unlock"].exists)
    }

    func testNoScreenSaysAWaterIsSafe() {
        let app = launch(["-skipIntro"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        for label in app.staticTexts.allElementsBoundByIndex.prefix(60).map(\.label) {
            let lower = label.lowercased()
            if lower.contains("safe") {
                XCTAssertTrue(lower.contains("not") || lower.contains("no "), label)
            }
        }
    }
}

/// Xcode's automated accessibility audit over every screen a person sees:
/// the lake list, a lake's own screen (the one that states the advisory
/// level), Favorites, About and the purchase sheet. It runs every check
/// (`.all`) at the default text size and again at the largest
/// accessibility size (AX5), where clipped text fails the test.
///
/// What fails (`Verdict.fail`): a contrast finding in the app's own
/// content, text clipped at AX5, and a missing description, hit region or
/// trait on the app's own elements. What is recorded without failing is
/// listed in `verdict(for:)`, each with its reason. Every audit attaches
/// its full list and a screenshot. Modeled on Trout Truck's
/// `AccessibilityAuditUITests`.
final class AccessibilityAuditUITests: XCTestCase {
    private static let ax5 = "UICTContentSizeCategoryAccessibilityXXXL"

    override func setUpWithError() throws { continueAfterFailure = true }

    func testEveryScreenAtTheDefaultTextSize() throws {
        try auditEveryScreen(contentSize: nil)
    }

    func testEveryScreenAtTheLargestAccessibilityTextSize() throws {
        try auditEveryScreen(contentSize: Self.ax5)
    }

    // MARK: -

    private func auditEveryScreen(contentSize: String?) throws {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-skipIntro", "-favorites", "ca-alameda-lake-temescal"]
        if let contentSize { app.launchArguments += ["-UIPreferredContentSizeCategoryName", contentSize] }
        app.launch()
        let label = contentSize == nil ? "default size" : "AX5"
        let isAX5 = contentSize != nil
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 30))

        try audit("Lakes", app: app, label: label, isAX5: isAX5)

        let search = app.searchFields.firstMatch
        reveal(search, in: app, down: true)
        focus(search, in: app)
        search.typeText("Temescal\n")
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Lake Temescal'")).firstMatch
        reveal(row, in: app)
        XCTAssertTrue(row.exists, "no row for Lake Temescal:\n\(app.debugDescription)")
        row.tap()
        XCTAssertTrue(app.buttons["favorite-button"].waitForExistence(timeout: 10), "the lake screen should open")
        // The full name is in the content, not only in a title that can truncate.
        XCTAssertEqual(app.staticTexts["lake-name"].label, "Lake Temescal")
        XCTAssertTrue(app.staticTexts["lake-name"].isHittable, "the name should show at the top of the lake screen")
        try audit("Lake detail", app: app, label: label, isAX5: isAX5)
        // At AX5 the history is several screens down; audit each screenful.
        for page in 1...(isAX5 ? 6 : 2) {
            app.collectionViews.firstMatch.swipeUp()
            try audit("Lake detail, scrolled \(page)", app: app, label: label, isAX5: isAX5)
        }

        select(tab: "Favorites", in: app)
        try audit("Favorites", app: app, label: label, isAX5: isAX5)

        let unlock = app.buttons["open-unlock"]
        reveal(unlock, in: app)
        XCTAssertTrue(unlock.exists, "Favorites should offer the unlock")
        unlock.tap()
        XCTAssertTrue(app.navigationBars["Unlock"].waitForExistence(timeout: 10), "the purchase sheet should open")
        // Let the sheet finish presenting; mid-animation it is dimmed.
        Thread.sleep(forTimeInterval: 2)
        try audit("Purchase sheet", app: app, label: label, isAX5: isAX5)
        app.collectionViews.firstMatch.swipeUp()
        try audit("Purchase sheet, scrolled", app: app, label: label, isAX5: isAX5)
        app.navigationBars["Unlock"].buttons["Close"].tap()

        select(tab: "About", in: app)
        try audit("About", app: app, label: label, isAX5: isAX5)
    }

    /// Taps a tab until its screen shows. At the largest text sizes the
    /// first tap can open the tab bar's large-content viewer instead.
    private func select(tab: String, in app: XCUIApplication) {
        for _ in 0..<3 {
            app.tabBars.buttons[tab].tap()
            if app.navigationBars[tab].waitForExistence(timeout: 5) { return }
        }
        XCTFail("the \(tab) tab didn't open:\n\(app.debugDescription)")
    }

    private func focus(_ field: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<3 {
            field.tap()
            if app.keyboards.firstMatch.waitForExistence(timeout: 5) { return }
        }
        XCTFail("the search field never took the keyboard")
    }

    /// Scrolls until the element exists and can be tapped; rows off screen
    /// don't exist. `down` scrolls toward the top first (the search field
    /// hides under a scrolled list).
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, down: Bool = false) {
        let list = app.collectionViews.firstMatch
        if down { for _ in 0..<8 where !(element.exists && element.isHittable) { list.swipeDown() } }
        for _ in 0..<8 where !(element.exists && element.isHittable) { list.swipeUp() }
        for _ in 0..<8 where !(element.exists && element.isHittable) { list.swipeDown() }
    }

    private enum Verdict {
        case fail
        case record(String)
    }

    private func audit(_ screen: String, app: XCUIApplication, label: String, isAX5: Bool) throws {
        // System chrome the audit samples through: the floating tab bar and
        // the fade above it, the keyboard, and the bars at the top.
        var chrome: [CGRect] = []
        let tabBar = app.tabBars.firstMatch
        if tabBar.exists, tabBar.isHittable {
            let top = tabBar.frame.minY - 120
            chrome.append(CGRect(x: 0, y: top, width: app.frame.width, height: app.frame.maxY - top))
        }
        if app.keyboards.firstMatch.exists { chrome.append(app.keyboards.firstMatch.frame) }
        // The navigation bar is chrome for sampled colors only: a title
        // truncated there is the app's own text, and fails at AX5.
        var topBar: CGRect?
        let navigationBar = app.navigationBars.firstMatch
        if navigationBar.exists {
            topBar = CGRect(x: 0, y: 0, width: app.frame.width, height: navigationBar.frame.maxY + 16)
        }

        var lines: [String] = []
        try app.performAccessibilityAudit(for: .all) { issue in
            let element = issue.element.map { "\($0.elementType.rawValue) '\($0.label)' \($0.frame)" } ?? "no element"
            let description = "\(issue.auditType.name): \(issue.compactDescription) - \(element)"
            switch Self.verdict(for: issue, chrome: chrome, topBar: topBar, screen: app.frame, isAX5: isAX5) {
            case .fail:
                lines.append("FAILED \(description)")
                return false
            case .record(let reason):
                lines.append("RECORDED (\(reason)) \(description)")
                return true
            }
        }
        let attachment = XCTAttachment(string: lines.isEmpty ? "no issues" : lines.joined(separator: "\n"))
        attachment.name = "\(screen) audit (\(label))"
        attachment.lifetime = .keepAlways
        add(attachment)
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "\(screen) screen (\(label))"
        shot.lifetime = .keepAlways
        add(shot)
    }

    private static func verdict(for issue: XCUIAccessibilityAuditIssue, chrome: [CGRect], topBar: CGRect?, screen: CGRect, isAX5: Bool) -> Verdict {
        guard let element = issue.element else {
            return .record("no element: the audit couldn't say what it saw")
        }
        let frame = element.frame
        if element.elementType == .searchField {
            return .record("iOS's own search field")
        }
        if !screen.contains(frame) {
            return .record("off screen, or partly: the audit samples pixels it can't see")
        }
        if chrome.contains(where: { $0.intersects(frame) }) {
            return .record("under the tab bar, its fade or the keyboard: the audit samples system chrome")
        }
        if let topBar, topBar.intersects(frame), issue.auditType != .textClipped {
            return .record("under the navigation bar or its fade: the audit samples system chrome")
        }
        if issue.auditType == .contrast, !element.isEnabled {
            return .record("a disabled control; WCAG 1.4.3 exempts inactive components")
        }
        switch issue.auditType {
        case .dynamicType:
            return .record("standard SwiftUI text styles, which scale; the AX5 pass audits the same screens at that size")
        case .textClipped where !isAX5:
            return .record("simulated by the audit at the default size; the AX5 pass fails on real clipping")
        default:
            return .fail
        }
    }
}

private extension XCUIAccessibilityAuditType {
    var name: String {
        switch self {
        case .contrast: return "contrast"
        case .elementDetection: return "elementDetection"
        case .hitRegion: return "hitRegion"
        case .sufficientElementDescription: return "sufficientElementDescription"
        case .dynamicType: return "dynamicType"
        case .textClipped: return "textClipped"
        case .trait: return "trait"
        default: return "other(\(rawValue))"
        }
    }
}

/// Screenshots for the hand-off and the App Store draft. Runs only when
/// SCREENSHOT_DIR is set (ios/scripts/screenshots.sh).
final class ScreenshotUITests: XCTestCase {
    func shoot(_ app: XCUIApplication, _ name: String) throws {
        guard let dir = ProcessInfo.processInfo.environment["SCREENSHOT_DIR"] else { return }
        try XCUIScreen.main.screenshot().pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
    }

    func testCaptureScreens() throws {
        guard ProcessInfo.processInfo.environment["SCREENSHOT_DIR"] != nil else { throw XCTSkip("SCREENSHOT_DIR not set") }
        let suffix = ProcessInfo.processInfo.environment["SCREENSHOT_SUFFIX"] ?? ""
        var app = XCUIApplication()
        app.launchArguments = ["-uiTesting"]
        app.launch()
        XCTAssertTrue(app.buttons["start-browsing"].waitForExistence(timeout: 10))
        try shoot(app, "app-01-intro\(suffix)")
        app.terminate()

        app = XCUIApplication()
        app.launchArguments = ["-uiTesting", "-skipIntro", "-entitled", "-favorites", "ca-alameda-lake-temescal,ca-lake-clear-lake,ca-el-dorado-lake-tahoe"]
        app.launch()
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        try shoot(app, "app-02-advisories\(suffix)")
        app.searchFields.firstMatch.tap()
        app.searchFields.firstMatch.typeText("Temescal")
        app.buttons.matching(NSPredicate(format: "label CONTAINS 'Lake Temescal'")).firstMatch.tap()
        _ = app.buttons["favorite-button"].waitForExistence(timeout: 5)
        try shoot(app, "app-03-lake\(suffix)")
        app.swipeUp()
        try shoot(app, "app-04-lake-dogs-and-spots\(suffix)")
        app.tabBars.buttons["Favorites"].tap()
        try shoot(app, "app-05-favorites\(suffix)")
        app.tabBars.buttons["About"].tap()
        try shoot(app, "app-06-about\(suffix)")
    }
}
