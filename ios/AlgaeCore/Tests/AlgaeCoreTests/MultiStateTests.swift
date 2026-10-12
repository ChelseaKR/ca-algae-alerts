import XCTest
@testable import AlgaeCore

/// California, Missouri and EPA CyAN in one snapshot, as the pipeline
/// builds it from the trap, Missouri and CyAN fixtures.
final class MultiStateTests: XCTestCase {
    func testBothStatesAndAllSourcesDecode() throws {
        let s = try Fixtures.multistate()
        XCTAssertEqual(Set(s.waterbodies.map(\.state)), ["CA", "MO"])
        XCTAssertEqual(s.sourceFiles.map(\.source), ["ca-swrcb-fhab", "mo-dnr-hab"])
        XCTAssertEqual(s.source(id: "epa-cyan")?.recordKind, .satelliteEstimate)
        XCTAssertEqual(s.advisorySource(state: "MO")?.liftSemantics, "explicit_field")
        XCTAssertTrue(s.advisorySource(state: "MO")?.requiredDisclaimer.hasPrefix("The data made available here") ?? false)
        XCTAssertEqual(s.advisorySource(state: "MO")?.revocable, true)
    }

    func testMissouriWordingAndPlace() throws {
        let s = try Fixtures.multistate()
        let dissipated = try XCTUnwrap(s.waterbodies.first { $0.status.liftKind == .dissipated })
        XCTAssertTrue(StatusWording.headline(dissipated.status).hasPrefix("The state recorded the bloom as dissipated on "))
        XCTAssertEqual(dissipated.countyLabel, "Missouri")
        let advisory = try XCTUnwrap(s.waterbodies.first { $0.state == "MO" && $0.status.kind == .advisory })
        XCTAssertEqual(StatusWording.guidance(for: advisory), StatusWording.genericGuidance)
        for w in s.waterbodies {
            XCTAssertEqual(affirmativeSafetyClaims(StatusWording.headline(w.status) + " " + StatusWording.dogAnswer(name: w.name, status: w.status)), [])
        }
    }

    func testSatelliteIsSeparateAndNeverAStatus() throws {
        let s = try Fixtures.multistate()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        let sat = try XCTUnwrap(alpha.satellite)
        XCTAssertEqual(sat.recordKind, .satelliteEstimate)
        XCTAssertEqual(sat.readings.first?.cellsPerMl, 554626)
        XCTAssertEqual(StatusWording.cellsLabel(554626), "about 550,000 cells/mL")
        XCTAssertEqual(StatusWording.cellsLabel(0), "below what the satellite can detect")
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        XCTAssertEqual(beta.satellite?.readings, [])
        XCTAssertEqual(beta.status.kind, .noAdvisoryRecorded, "an empty satellite series changes nothing")
        XCTAssertEqual(affirmativeSafetyClaims(StatusWording.satelliteExplainer), [])
    }

    func testDecoderRefusesASatelliteBlockPosingAsAnAdvisory() throws {
        var json = try XCTUnwrap(String(data: Fixtures.multistateData(), encoding: .utf8))
        json = json.replacingOccurrences(of: #""record_kind":"satellite_estimate","cyan_name""#, with: #""record_kind":"official_advisory","cyan_name""#)
        XCTAssertThrowsError(try SnapshotDecoder.decode(Data(json.utf8)))
    }

    func testAlertPlannerTreatsMissouriLikeAnyAdvisory() throws {
        let s = try Fixtures.multistate()
        let water = try XCTUnwrap(s.waterbodies.first { $0.state == "MO" && $0.status.kind == .noAdvisoryRecorded })
        let first = AlertPlanner.plan(favorites: [water.id], snapshot: s, baseline: AlertBaseline())
        let reopened = Fixtures.replacing(water.id, status: Status(kind: .advisory, tier: .otherAdvisory, level: "Advisory (advise)", posted: PlainDate(year: 2026, month: 10, day: 11), sitesWithAdvisory: 1), in: s)
        let plan = AlertPlanner.plan(favorites: [water.id], snapshot: reopened, baseline: first.baseline)
        XCTAssertEqual(plan.notifications.first?.title, "Advisory (advise): \(water.name)")
    }
}
