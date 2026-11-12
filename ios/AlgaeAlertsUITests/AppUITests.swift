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
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH[c] 'Posted in the 30 days to '")).firstMatch.exists)
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

    /// The lake screen opens on its posted notice: the level's words and
    /// rank, read aloud, and a way to share the lake's web page.
    func testALakeShowsItsSignAndCanBeShared() {
        let app = launch(["-skipIntro"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        app.searchFields.firstMatch.tap()
        app.searchFields.firstMatch.typeText("Temescal")
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Lake Temescal'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        XCTAssertTrue(row.label.contains("sign") || row.label.contains("Latest state record"), "the row speaks its sign: \(row.label)")
        row.tap()
        let sign = app.descendants(matching: .any)["lake-sign"]
        XCTAssertTrue(sign.waitForExistence(timeout: 5))
        XCTAssertTrue(sign.label.hasSuffix("of 3 marks") || sign.label.hasSuffix("not an advisory") || sign.label.hasSuffix(" sign"), sign.label)
        let share = app.buttons["share-lake"]
        XCTAssertTrue(share.exists)
        XCTAssertEqual(share.label, "Share Lake Temescal")
        share.tap()
        // The system share sheet, whatever iOS version draws it.
        let sheet = app.otherElements["ActivityListView"]
        let copy = app.buttons["Copy"]
        XCTAssertTrue(sheet.waitForExistence(timeout: 10) || copy.waitForExistence(timeout: 5), "the share sheet should open:\n\(app.debugDescription)")
    }

    func testASearchWithNoMatchSaysSoInWords() {
        let app = launch(["-skipIntro"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        app.searchFields.firstMatch.tap()
        app.searchFields.firstMatch.typeText("Qqqzx")
        let title = app.staticTexts["No lake matches \u{201C}Qqqzx\u{201D}"]
        XCTAssertTrue(title.waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'That is not a finding about the water'")).firstMatch.exists)
    }

    func testEmptyFavoritesOfferTheLakeList() {
        let app = launch(["-skipIntro"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        app.tabBars.buttons["Favorites"].tap()
        XCTAssertTrue(app.staticTexts["No saved lakes yet"].waitForExistence(timeout: 5))
        let browse = app.buttons["browse-lakes"]
        XCTAssertTrue(browse.exists)
        browse.tap()
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 5))
    }

    /// No data on the phone and no network: the screen says which, in
    /// words, and offers to try again. Nothing reads as a lake's status.
    func testNoDataOfflineStateSaysWhatHappened() {
        let app = launch(["-skipIntro", "-noBundledSnapshot", "-simulateOffline"])
        XCTAssertTrue(app.staticTexts["This iPhone is offline"].waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(app.buttons["retry-load"].exists)
        XCTAssertFalse(app.buttons.matching(NSPredicate(format: "label CONTAINS 'advisory'")).firstMatch.exists)
    }

    func testNoDataOnlineStateSaysTheReadFailed() {
        let app = launch(["-skipIntro", "-noBundledSnapshot"])
        XCTAssertTrue(app.staticTexts["No lake records on this iPhone"].waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(app.buttons["retry-load"].exists)
    }

    /// Offline with data: the list stays, with the file's date said aloud.
    func testOfflineWithDataKeepsTheListAndSaysItsDate() {
        let app = launch(["-skipIntro", "-simulateOffline"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        let banner = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'This iPhone is offline. Showing the copy already on it, from the data file dated'")).firstMatch
        XCTAssertTrue(banner.waitForExistence(timeout: 5), app.debugDescription)
    }

    func testAboutHasASupportRow() {
        let app = launch(["-skipIntro"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        app.tabBars.buttons["About"].tap()
        let support = app.descendants(matching: .any)["contact-support"]
        for _ in 0..<8 where !(support.exists && support.isHittable) { app.collectionViews.firstMatch.swipeUp() }
        XCTAssertTrue(support.exists)
        XCTAssertEqual(support.label, "Email support at chelsea@chelseakr.com")
        XCTAssertTrue(app.buttons["share-app"].exists)
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
        // Let the push finish; mid-animation the screen is dimmed.
        Thread.sleep(forTimeInterval: 2)
        // The full name is in the content, not only in a title that can truncate.
        XCTAssertEqual(app.staticTexts["lake-name"].label, "Lake Temescal")
        XCTAssertTrue(app.staticTexts["lake-name"].isHittable, "the name should show at the top of the lake screen")
        try audit("Lake detail", app: app, label: label, isAX5: isAX5)
        // At AX5 the history is several screens down; audit each screenful.
        for page in 1...(isAX5 ? 6 : 2) {
            app.collectionViews.firstMatch.swipeUp()
            Thread.sleep(forTimeInterval: 1)
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
        app.terminate()

        // The designed empty and offline screens (DECISIONS 0036).
        let empty = XCUIApplication()
        empty.launchArguments = ["-uiTesting", "-skipIntro", "-noBundledSnapshot", "-simulateOffline"]
        if let contentSize { empty.launchArguments += ["-UIPreferredContentSizeCategoryName", contentSize] }
        empty.launch()
        XCTAssertTrue(empty.staticTexts["This iPhone is offline"].waitForExistence(timeout: 30))
        try audit("No data, offline", app: empty, label: label, isAX5: isAX5)
        select(tab: "Favorites", in: empty)
        try audit("Favorites, empty", app: empty, label: label, isAX5: isAX5)
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
            // Plus the scroll-edge fade iOS draws under the bar.
            topBar = CGRect(x: 0, y: 0, width: app.frame.width, height: navigationBar.frame.maxY + 44)
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
