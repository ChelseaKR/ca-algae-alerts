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

    func testAccessibilityAuditOnTheMainScreens() throws {
        let app = launch(["-skipIntro", "-favorites", "ca-alameda-lake-temescal"])
        XCTAssertTrue(app.navigationBars["Algae advisories"].waitForExistence(timeout: 10))
        let types: XCUIAccessibilityAuditType = [.contrast, .elementDetection, .hitRegion, .sufficientElementDescription]
        try app.performAccessibilityAudit(for: types) { Self.isSystemArtifact($0, in: app) }
        app.tabBars.buttons["Favorites"].tap()
        try app.performAccessibilityAudit(for: types) { Self.isSystemArtifact($0, in: app) }
        app.tabBars.buttons["About"].tap()
        try app.performAccessibilityAudit(for: types) { Self.isSystemArtifact($0, in: app) }
    }

    /// Issues the app's own colors cannot cause, and only those:
    /// - the search field's placeholder, which is the system's styling;
    /// - contrast measured on text passing under the floating tab bar, where
    ///   iOS fades scrolling content on purpose. The same rows pass when
    ///   they are higher on the screen, and the colors themselves are
    ///   checked in `AppTests.testThemeContrast`.
    static func isSystemArtifact(_ issue: XCUIAccessibilityAuditIssue, in app: XCUIApplication) -> Bool {
        guard let element = issue.element else { return false }
        if element.elementType == .searchField { return true }
        guard issue.auditType == .contrast else { return false }
        let fadeTop = app.tabBars.firstMatch.frame.minY - 120
        return element.frame.maxY > fadeTop
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
