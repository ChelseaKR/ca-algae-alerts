import XCTest
@testable import AlgaeCore

/// The posted-sign band, sharing, the review rule and the empty-state words
/// (DECISIONS 0036).
final class PostedNoticeTests: XCTestCase {
    let posted = PlainDate(year: 2026, month: 9, day: 20)

    func advisory(_ tier: AdvisoryTier?, level: String = "") -> Status {
        Status(kind: .advisory, tier: tier, level: level, posted: posted, sitesWithAdvisory: 1)
    }

    func testCaliforniaLevelsGetTheirSignAndRank() {
        let cases: [(AdvisoryTier, NoticeBand.Paint, Int, String)] = [
            (.caution, .caution, 1, "Caution advisory"),
            (.warning, .warning, 2, "Warning advisory"),
            (.danger, .danger, 3, "Danger advisory"),
        ]
        for (tier, paint, rank, words) in cases {
            let band = NoticeBand(advisory(tier))
            XCTAssertEqual(band.paint, paint)
            XCTAssertEqual(band.rank, rank)
            XCTAssertEqual(band.words, words)
            XCTAssertEqual(band.spoken, "\(words) sign, \(rank) of 3 marks")
            XCTAssertTrue(band.isAdvisory)
        }
        XCTAssertTrue(NoticeBand(advisory(.danger)).heavyEdge)
        XCTAssertFalse(NoticeBand(advisory(.warning)).heavyEdge)
    }

    func testOffScaleAdvisoriesKeepTheStatesWordsAndNoRank() {
        let band = NoticeBand(advisory(.otherAdvisory, level: "Algal mat alert sign"))
        XCTAssertEqual(band.paint, .otherAdvisory)
        XCTAssertNil(band.rank)
        XCTAssertEqual(band.words, "Algal mat alert sign")
        XCTAssertEqual(band.spoken, "Algal mat alert sign sign")
    }

    /// Nothing that is not an advisory takes a level color or a level word.
    func testARecordThatIsNotAnAdvisoryIsNeutral() {
        let statuses = [
            Status(kind: .noAdvisoryRecorded, liftKind: .noAdvisoryRecord, liftDate: posted),
            Status(kind: .noAdvisoryRecorded, liftKind: .dissipated, liftDate: posted),
            Status(kind: .noAdvisoryRecorded, liftKind: .endDate, liftDate: posted),
            Status(kind: .undetermined),
            Status(kind: .undetermined, level: "Danger - Closure"),
        ]
        for status in statuses {
            let band = NoticeBand(status)
            XCTAssertEqual(band.paint, .record, "\(status)")
            XCTAssertNil(band.rank)
            XCTAssertEqual(band.words, "Latest state record")
            XCTAssertFalse(band.heavyEdge)
            XCTAssertEqual(band.spoken, "Latest state record, not an advisory")
            XCTAssertEqual(affirmativeSafetyClaims(band.spoken), [])
        }
    }

    func testRecordRowsUseTheSameBands() throws {
        let snapshot = try Fixtures.traps()
        for record in snapshot.waterbodies.flatMap(\.records) {
            let band = NoticeBand(record: record)
            XCTAssertEqual(band.isAdvisory, record.tier.isAdvisory, record.id)
        }
    }

    func testSharingSendsTheLakesWebPage() throws {
        let water = try XCTUnwrap(Fixtures.traps().waterbodies.first)
        XCTAssertEqual(LakeShare.url(for: water.id).absoluteString, "https://lakenotice.com/water/\(water.id)/")
        XCTAssertTrue(LakeShare.subject(water).hasPrefix(water.name))
        XCTAssertEqual(affirmativeSafetyClaims(LakeShare.message(water)), [])
        XCTAssertFalse(LakeShare.message(water).lowercased().contains("safe"))
    }

    func testTheReviewAskWaitsForRealUse() {
        var ask = ReviewAsk()
        XCTAssertFalse(ask.shouldAsk(justSavedALake: true, favoriteCount: 5, version: "1.0.0"), "never on a first day")
        for day in [1, 1, 2] { ask.noteOpened(on: PlainDate(year: 2026, month: 11, day: day)) }
        XCTAssertEqual(ask.daysOpened.count, 2, "one count per calendar day")
        ask.noteOpened(on: PlainDate(year: 2026, month: 11, day: 3))
        XCTAssertFalse(ask.shouldAsk(justSavedALake: false, favoriteCount: 5, version: "1.0.0"), "only right after saving a lake")
        XCTAssertFalse(ask.shouldAsk(justSavedALake: true, favoriteCount: 1, version: "1.0.0"), "one saved lake is not enough")
        XCTAssertTrue(ask.shouldAsk(justSavedALake: true, favoriteCount: 2, version: "1.0.0"))
        ask.noteAsked(version: "1.0.0")
        XCTAssertFalse(ask.shouldAsk(justSavedALake: true, favoriteCount: 3, version: "1.0.0"), "once per version")
        XCTAssertTrue(ask.shouldAsk(justSavedALake: true, favoriteCount: 3, version: "1.1.0"))
    }

    func testTheReviewAskKeepsOnlyRecentDays() throws {
        var ask = ReviewAsk()
        for day in 1...20 { ask.noteOpened(on: PlainDate(year: 2026, month: 11, day: day)) }
        XCTAssertEqual(ask.daysOpened.count, 7)
        XCTAssertEqual(ask.daysOpened.last, "2026-11-20")
        let data = try JSONEncoder().encode(ask)
        XCTAssertEqual(try JSONDecoder().decode(ReviewAsk.self, from: data), ask)
    }

    func testTheReviewAskStoreReadsEmptyWhenMissingOrCorrupt() throws {
        let layout = try Fixtures.tempLayout()
        let stores = AppStores(layout: layout)
        XCTAssertEqual(stores.reviewAsk(), ReviewAsk())
        try Data("not json".utf8).write(to: layout.reviewAskFile)
        XCTAssertEqual(stores.reviewAsk(), ReviewAsk())
        var ask = ReviewAsk()
        ask.noteAsked(version: "1.0.0")
        try stores.save(ask)
        XCTAssertEqual(stores.reviewAsk().askedInVersion, "1.0.0")
    }

    func testEmptyStateWordsNeverMakeAFinding() {
        let all = [
            EmptyCopy.noDataTitle, EmptyCopy.noDataMessage, EmptyCopy.offlineTitle, EmptyCopy.offlineNoDataMessage,
            EmptyCopy.offlineBanner(fileDate: posted), EmptyCopy.noMatchTitle("Zz"), EmptyCopy.noMatchMessage,
            EmptyCopy.noFavoritesTitle, EmptyCopy.noFavoritesMessage, EmptyCopy.goneTitle, EmptyCopy.goneMessage,
        ]
        for text in all { XCTAssertEqual(affirmativeSafetyClaims(text), [], text) }
        XCTAssertTrue(EmptyCopy.offlineBanner(fileDate: posted).contains("Sep 20, 2026"), "the offline banner carries the file's date")
        XCTAssertEqual(EmptyCopy.noMatchTitle("  Temescal "), "No lake matches \u{201C}Temescal\u{201D}")
    }

    func testSupportMailNamesTheApp() {
        let url = SupportContact.mailURL(version: "1.0.0")
        XCTAssertEqual(url.scheme, "mailto")
        XCTAssertTrue(url.absoluteString.hasPrefix("mailto:chelsea@chelseakr.com?subject="))
        XCTAssertTrue(url.absoluteString.contains("Lake%20Notice%20for%20iPhone%201.0.0"))
        XCTAssertTrue(SupportContact.mailURL(version: nil).absoluteString.hasSuffix("subject=Lake%20Notice%20for%20iPhone"), "no made-up version")
    }
}
