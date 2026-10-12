import Foundation
import XCTest
@testable import AlgaeCore

enum Fixtures {
    static func trapsData() throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "traps-snapshot", withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    static func traps() throws -> Snapshot { try SnapshotDecoder.decode(trapsData()) }

    static func multistateData() throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "multistate-snapshot", withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    static func multistate() throws -> Snapshot { try SnapshotDecoder.decode(multistateData()) }

    static func water(_ name: String, in snapshot: Snapshot) throws -> Waterbody {
        try XCTUnwrap(snapshot.waterbodies.first { $0.name == name })
    }

    /// The trap snapshot with one water's status replaced.
    static func replacing(_ id: Waterbody.ID, status: Status, in snapshot: Snapshot) -> Snapshot {
        let waters = snapshot.waterbodies.map { w in
            w.id == id ? Waterbody(id: w.id, state: w.state, name: w.name, countyText: w.countyText, counties: w.counties, center: w.center, status: status, sites: w.sites, records: w.records, satellite: w.satellite) : w
        }
        return Snapshot(schemaVersion: snapshot.schemaVersion, generatedAt: snapshot.generatedAt, runDate: snapshot.runDate, sources: snapshot.sources, sourceFile: snapshot.sourceFile, sourceFiles: snapshot.sourceFiles, waterbodies: waters)
    }

    static func tempLayout() throws -> AppStorageLayout {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return AppStorageLayout(directory: dir)
    }
}

/// Sentences that mention safety or an all-clear without negating it or
/// asking it. The same rule as the site's copy guard.
func affirmativeSafetyClaims(_ text: String) -> [String] {
    let sentences = text.components(separatedBy: CharacterSet(charactersIn: ".!?")).map { $0.trimmingCharacters(in: .whitespaces) }
    let safety = try! NSRegularExpression(pattern: #"\b(safe|safety|all[- ]clear)\b"#, options: .caseInsensitive)
    let negation = try! NSRegularExpression(pattern: #"\b(not|never|no|cannot)\b|n't\b"#, options: .caseInsensitive)
    return sentences.filter { s in
        let r = NSRange(s.startIndex..., in: s)
        return safety.firstMatch(in: s, range: r) != nil && negation.firstMatch(in: s, range: r) == nil
    }
}
