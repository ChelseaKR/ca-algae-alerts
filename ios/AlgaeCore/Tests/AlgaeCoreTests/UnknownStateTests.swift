import Foundation
import XCTest
@testable import AlgaeCore

/// A state this build does not know must not stop updates for the states it
/// does (launch-readiness 2026-11-05 §3, DECISIONS 0030).
final class UnknownStateTests: XCTestCase {
    /// The multistate fixture plus a New York source, file, state-status
    /// entry and water, all in a record kind this build has never seen.
    private func withNewYork(state: String = "NY") throws -> Data {
        var root = try XCTUnwrap(JSONSerialization.jsonObject(with: Fixtures.multistateData()) as? [String: Any])
        var sources = try XCTUnwrap(root["sources"] as? [[String: Any]])
        var ny = try XCTUnwrap(sources.first)
        ny["id"] = "ny-dec-hab"
        ny["state"] = state
        ny["record_kind"] = "bloom_history"
        sources.append(ny)
        root["sources"] = sources
        var files = try XCTUnwrap(root["source_files"] as? [[String: Any]])
        var file = try XCTUnwrap(files.first)
        file["source"] = "ny-dec-hab"
        files.append(file)
        root["source_files"] = files
        root["state_status"] = [["state": state, "mode": "a_mode_from_later", "since": "2026-11-01"]]
        var waters = try XCTUnwrap(root["waterbodies"] as? [[String: Any]])
        var water = try XCTUnwrap(waters.first)
        water["id"] = "ny-lake-champlain"
        water["state"] = state
        water["name"] = "Lake Champlain"
        var status = try XCTUnwrap(water["status"] as? [String: Any])
        status["kind"] = "bloom_seen"
        water["status"] = status
        var records = try XCTUnwrap(water["records"] as? [[String: Any]])
        if !records.isEmpty { records[0]["record_kind"] = "bloom_history" }
        water["records"] = records
        waters.append(water)
        root["waterbodies"] = waters
        return try JSONSerialization.data(withJSONObject: root)
    }

    func testTheInjectedStateWouldBreakAPlainDecode() throws {
        // The sabotage applies: without the filter this file does not decode.
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        XCTAssertThrowsError(try decoder.decode(Snapshot.self, from: withNewYork()))
    }

    func testAnUnknownStateIsLeftOutAndTheKnownStatesStillDecode() throws {
        let plain = try Fixtures.multistate()
        let s = try SnapshotDecoder.decode(withNewYork())
        XCTAssertEqual(s.waterbodies, plain.waterbodies)
        XCTAssertFalse(s.waterbodies.contains { $0.state == "NY" })
        XCTAssertFalse(s.sources.contains { $0.id == "ny-dec-hab" })
        XCTAssertFalse(s.sourceFiles.contains { $0.source == "ny-dec-hab" })
        XCTAssertEqual(s.sources, plain.sources, "California, Missouri and EPA CyAN stay")
    }

    func testAKnownStateIsStillDecodedStrictly() throws {
        // The same water, labeled California, is refused as before.
        XCTAssertThrowsError(try SnapshotDecoder.decode(withNewYork(state: "CA")))
    }

    func testAFileWithNothingUnknownIsDecodedFromItsOwnBytes() throws {
        let data = try Fixtures.multistateData()
        XCTAssertEqual(try SnapshotDecoder.knownStatesOnly(data), data)
    }
}
