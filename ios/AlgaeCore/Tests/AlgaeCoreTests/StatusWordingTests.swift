import XCTest
@testable import AlgaeCore

/// Pins the sentences to the website's (`pipeline/src/caalgae/wording.py`)
/// and checks that nothing the app says claims a water is safe.
final class StatusWordingTests: XCTestCase {
    let advisory = Status(kind: .advisory, tier: .caution, level: "Caution", posted: PlainDate(year: 2026, month: 9, day: 20), sitesWithAdvisory: 1)
    let lifted = Status(kind: .noAdvisoryRecorded, liftKind: .noAdvisoryRecord, liftDate: PlainDate(year: 2026, month: 9, day: 1))
    let ended = Status(kind: .noAdvisoryRecorded, liftKind: .endDate, liftDate: PlainDate(year: 2025, month: 9, day: 30))
    let undetermined = Status(kind: .undetermined)
    let unrecognized = Status(kind: .undetermined, level: "Danger - Closure")

    func testHeadlinesMatchTheWebsite() {
        XCTAssertEqual(StatusWording.headline(advisory), "Caution advisory, last posted Sep 20, 2026. No all-clear recorded.")
        XCTAssertEqual(StatusWording.headline(lifted), "The state's latest record, from Sep 1, 2026, recommends no advisory.")
        XCTAssertEqual(StatusWording.headline(ended), "The state recorded an end date of Sep 30, 2025.")
        XCTAssertEqual(StatusWording.headline(undetermined), "Reports on file, with no advisory level the state has classified.")
        XCTAssertEqual(StatusWording.headline(unrecognized), "The state's latest record says \u{201C}Danger - Closure\u{201D}, a level this site does not recognize, so it cannot say what applies. Check the official map.")
        XCTAssertEqual(StatusWording.dogAnswer(name: "X", status: unrecognized), "The state's latest record says \u{201C}Danger - Closure\u{201D}, a level this site does not recognize, so it cannot say what applies. Check the official map. Until it is read, keep your dog out of the water at X and away from scum on the shore.")
        XCTAssertFalse(StatusWording.shortLine(unrecognized).contains("No advisory"))
    }

    func testOtherAdvisoryUsesTheStatesOwnWords() {
        let mat = Status(kind: .advisory, tier: .otherAdvisory, level: "Algal mat alert sign", posted: PlainDate(year: 2026, month: 9, day: 25), sitesWithAdvisory: 1)
        XCTAssertEqual(StatusWording.levelName(mat), "Algal mat alert sign")
    }

    func testGuidanceKeepsPetsOutAndMatsGetTheirOwn() {
        for tier in [AdvisoryTier.caution, .warning, .danger] {
            XCTAssertTrue(StatusWording.guidance(tier).contains("go into or drink the water"), "\(tier)")
            XCTAssertTrue(StatusWording.guidance(tier).contains("boiling or filtering does not make it safe"), "\(tier)")
        }
        XCTAssertTrue(StatusWording.isAlgalMat("Algal mat general awareness sign"))
        XCTAssertFalse(StatusWording.isAlgalMat("General awareness"))
        XCTAssertTrue(StatusWording.algalMatGuidance.contains("Do not let dogs eat algal mats or drink from the water"))
        XCTAssertEqual(affirmativeSafetyClaims(StatusWording.algalMatGuidance), [])
        XCTAssertEqual(affirmativeSafetyClaims(StatusWording.stateGuidance["MO"] ?? ""), [])
    }

    func testNothingTheAppSaysClaimsSafety() throws {
        var lines: [String] = [StatusWording.dogAdvice, StatusWording.humanAdvice, StatusWording.notMedicalAdvice, FreeTier.unlockSummary]
        for s in [advisory, lifted, ended, undetermined, unrecognized] {
            lines += [StatusWording.headline(s), StatusWording.shortLine(s), StatusWording.caveat(s), StatusWording.dogAnswer(name: "X", status: s)]
        }
        lines += AdvisoryTier.allCases.map(StatusWording.guidance)
        let snapshot = try Fixtures.traps()
        for w in snapshot.waterbodies {
            lines += [StatusWording.headline(w.status), StatusWording.dogAnswer(name: w.name, status: w.status)]
        }
        for line in lines { XCTAssertEqual(affirmativeSafetyClaims(line), [], line) }
    }

    func testHumanAndMedicalLinesMatchTheWebsite() {
        XCTAssertEqual(StatusWording.humanAdvice, "If you or a child go in water that may have toxic algae, shower or rinse off with tap water right away. If anyone gets sick afterward, call a doctor or Poison Control at 1-800-222-1222.")
        XCTAssertEqual(StatusWording.notMedicalAdvice, "Lake Notice republishes state records for information only. It is not medical advice, and records can be late or wrong. In an emergency, call 911. For a possible poisoning, call Poison Control at 1-800-222-1222.")
    }

    func testGuardIsNotVacuous() {
        XCTAssertEqual(affirmativeSafetyClaims("Lake X is safe for dogs."), ["Lake X is safe for dogs"])
        XCTAssertEqual(affirmativeSafetyClaims("All-clear recorded."), ["All-clear recorded"])
    }

    func testLiftNeverUsesAdvisoryWording() {
        XCTAssertFalse(StatusWording.shortLine(lifted).contains("Caution"))
        XCTAssertTrue(StatusWording.shortLine(lifted).contains("Sep 1, 2026"))
    }

    /// VoiceOver reads " · " aloud, so the spoken line uses a comma and
    /// keeps every other word.
    func testSpokenShortLineDropsTheSeparator() {
        XCTAssertEqual(StatusWording.shortLine(advisory), "Caution advisory · posted Sep 20, 2026")
        XCTAssertEqual(StatusWording.spokenShortLine(advisory), "Caution advisory, posted Sep 20, 2026")
        XCTAssertEqual(StatusWording.spokenShortLine(lifted), "No advisory in latest record, Sep 1, 2026")
        for s in [advisory, lifted] { XCTAssertFalse(StatusWording.spokenShortLine(s).contains("·")) }
    }
}
