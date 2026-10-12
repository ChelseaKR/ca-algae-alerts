import XCTest
@testable import AlgaeCore

final class SnapshotDecoderTests: XCTestCase {
    func testDecodesThePipelinesTrapSnapshot() throws {
        let s = try Fixtures.traps()
        XCTAssertEqual(s.schemaVersion, 1)
        XCTAssertEqual(s.waterbodies.count, 9)
        XCTAssertEqual(s.sources.first?.license, "Other (Public Domain)")
        XCTAssertEqual(s.sourceFile.fileDate, PlainDate(year: 2026, month: 10, day: 9))
    }

    func testStatusesSurviveDecoding() throws {
        let s = try Fixtures.traps()
        let alpha = try Fixtures.water("Lake Alpha", in: s)
        XCTAssertEqual(alpha.status.kind, .advisory)
        XCTAssertEqual(alpha.status.tier, .caution)
        XCTAssertEqual(alpha.status.posted, PlainDate(year: 2026, month: 9, day: 20))
        XCTAssertNil(alpha.records.first?.endDate, "a blank end date stays unknown")
        let beta = try Fixtures.water("Beta Reservoir", in: s)
        XCTAssertEqual(beta.status.kind, .noAdvisoryRecorded)
        XCTAssertEqual(beta.status.liftKind, .noAdvisoryRecord)
        XCTAssertEqual(try Fixtures.water("Theta Lake", in: s).status.kind, .undetermined)
        XCTAssertEqual(try Fixtures.water("Delta Lake", in: s).status.tier, .otherAdvisory)
    }

    func testRefusesAnAdvisoryWithoutAPostedDate() throws {
        var json = try XCTUnwrap(String(data: Fixtures.trapsData(), encoding: .utf8))
        json = json.replacingOccurrences(of: #""posted":"2026-09-20""#, with: #""posted":null"#)
        XCTAssertThrowsError(try SnapshotDecoder.decode(Data(json.utf8)))
    }

    func testRefusesAnUnknownStatusKind() throws {
        var json = try XCTUnwrap(String(data: Fixtures.trapsData(), encoding: .utf8))
        json = json.replacingOccurrences(of: #""kind":"no_advisory_recorded""#, with: #""kind":"safe""#)
        XCTAssertThrowsError(try SnapshotDecoder.decode(Data(json.utf8)))
    }

    func testRefusesAnotherSchemaVersion() throws {
        var json = try XCTUnwrap(String(data: Fixtures.trapsData(), encoding: .utf8))
        json = json.replacingOccurrences(of: #""schema_version":1"#, with: #""schema_version":2"#)
        XCTAssertThrowsError(try SnapshotDecoder.decode(Data(json.utf8))) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .unsupportedSchemaVersion(2))
        }
    }

    func testPlainDate() {
        XCTAssertEqual(PlainDate(iso: "2026-10-09")?.label, "Oct 9, 2026")
        XCTAssertNil(PlainDate(iso: "2026-13-01"))
        XCTAssertEqual(PlainDate(year: 2026, month: 9, day: 1).days(until: PlainDate(year: 2026, month: 10, day: 1)), 30)
    }
}
