import Foundation

public enum SnapshotDecodingError: Error, Equatable, CustomStringConvertible {
    case unsupportedSchemaVersion(Int)
    case invariant(String)

    public var description: String {
        switch self {
        case .unsupportedSchemaVersion(let v): "unsupported snapshot schema version \(v)"
        case .invariant(let message): message
        }
    }
}

/// Strict decoding: an unknown status kind or tier is an error, not a
/// default, and the schema's own rules are checked again here, so a file
/// that would make the app say something the records do not support is
/// refused and the copy already on the phone is kept.
///
/// The strictness covers the states this build knows. A state it does not
/// know (a later build's New York, say) is left out before decoding, with its
/// sources and files, so a shipped app keeps updating its own states when a
/// new one is published (DECISIONS 0030). A new state reaches the app only in
/// a build that knows it.
public enum SnapshotDecoder {
    /// The states this build shows. Everything else in a file is ignored.
    public static let knownStates: Set<String> = Set(Waterbody.stateNames.keys)
    /// A national source (EPA CyAN) carries "US", not a state.
    static let nationalSourceState = "US"

    public static func decode(_ data: Data) throws -> Snapshot {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let snapshot = try decoder.decode(Snapshot.self, from: knownStatesOnly(data))
        guard snapshot.schemaVersion == 1 else {
            throw SnapshotDecodingError.unsupportedSchemaVersion(snapshot.schemaVersion)
        }
        for water in snapshot.waterbodies {
            try check(water.status, at: water.id)
            guard water.records.allSatisfy({ $0.recordKind == .officialAdvisory }) else {
                throw SnapshotDecodingError.invariant("\(water.id): only official advisories may be advisory records")
            }
            if let satellite = water.satellite, satellite.recordKind != .satelliteEstimate {
                throw SnapshotDecodingError.invariant("\(water.id): a satellite block must be a satellite estimate")
            }
            for site in water.sites { try check(site.status, at: "\(water.id)/\(site.id)") }
        }
        for entry in snapshot.stateStatus ?? [] where entry.mode == .unavailable && entry.since == nil {
            throw SnapshotDecodingError.invariant("\(entry.state): an unavailable state needs its since date")
        }
        return snapshot.maskingUnavailable()
    }

    /// The file with every state this build does not know removed: its
    /// waterbodies, its sources, its source files and its state-status
    /// entries. A source whose record kind this build does not know is
    /// removed too. Anything else, including a known state's water with an
    /// unknown kind, is left for the strict decode to refuse. When nothing is
    /// removed the original bytes are decoded unchanged.
    static func knownStatesOnly(_ data: Data) throws -> Data {
        guard var root = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return data
        }
        var removed = false
        func keep(_ key: String, where include: ([String: Any]) -> Bool) {
            guard let items = root[key] as? [Any] else { return }
            let kept = items.filter { item in
                guard let object = item as? [String: Any] else { return true }
                return include(object)
            }
            if kept.count != items.count {
                removed = true
                root[key] = kept
            }
        }
        func known(_ object: [String: Any]) -> Bool {
            guard let state = object["state"] as? String else { return true }
            return knownStates.contains(state)
        }
        keep("waterbodies", where: known)
        keep("state_status", where: known)
        keep("sources") { source in
            if let kind = source["record_kind"] as? String, RecordKind(rawValue: kind) == nil { return false }
            guard let state = source["state"] as? String else { return true }
            return knownStates.contains(state) || state == nationalSourceState
        }
        let sourceIDs = Set(((root["sources"] as? [Any]) ?? []).compactMap { ($0 as? [String: Any])?["id"] as? String })
        keep("source_files") { file in
            guard let source = file["source"] as? String else { return true }
            return sourceIDs.contains(source)
        }
        guard removed else { return data }
        return try JSONSerialization.data(withJSONObject: root)
    }

    static func check(_ status: Status, at place: String) throws {
        switch status.kind {
        case .advisory:
            guard status.tier != nil, status.posted != nil, status.liftDate == nil else {
                throw SnapshotDecodingError.invariant("\(place): an advisory needs a tier and a posted date, and no lift")
            }
        case .noAdvisoryRecorded:
            guard status.liftKind != nil, status.liftDate != nil, status.tier == nil else {
                throw SnapshotDecodingError.invariant("\(place): an end needs a recorded kind and date")
            }
        case .undetermined:
            guard status.tier == nil, status.liftDate == nil else {
                throw SnapshotDecodingError.invariant("\(place): undetermined carries no tier or lift")
            }
        }
    }
}
