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
public enum SnapshotDecoder {
    public static func decode(_ data: Data) throws -> Snapshot {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let snapshot = try decoder.decode(Snapshot.self, from: data)
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
        return snapshot
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
