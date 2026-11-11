import Foundation

/// The snapshot the pipeline publishes (`schema/snapshot.v1.json`). Every
/// status in it was derived from explicit state records only: an advisory
/// stands until the state records an end, and nothing in it means "safe".
public struct Snapshot: Codable, Equatable, Sendable {
    public let schemaVersion: Int
    public let generatedAt: String
    public let runDate: PlainDate
    public let sources: [DataSource]
    public let sourceFile: SourceFile
    /// Every advisory source's last read file (California first).
    public let sourceFiles: [SourceFile]
    public let waterbodies: [Waterbody]
    /// How current each state's data is (DECISIONS 0024). Absent in files
    /// written before it existed, which means every state is live.
    public let stateStatus: [StateStatus]?

    public init(schemaVersion: Int, generatedAt: String, runDate: PlainDate, sources: [DataSource], sourceFile: SourceFile, sourceFiles: [SourceFile], waterbodies: [Waterbody], stateStatus: [StateStatus]? = nil) {
        self.stateStatus = stateStatus
        self.schemaVersion = schemaVersion
        self.generatedAt = generatedAt
        self.runDate = runDate
        self.sources = sources
        self.sourceFile = sourceFile
        self.sourceFiles = sourceFiles
        self.waterbodies = waterbodies
    }

    public func source(id: String) -> DataSource? { sources.first { $0.id == id } }

    /// The official-advisory source for a state.
    public func advisorySource(state: String) -> DataSource? {
        sources.first { $0.state == state && $0.recordKind == .officialAdvisory }
    }

    public func waterbody(id: Waterbody.ID) -> Waterbody? { waterbodies.first { $0.id == id } }

    enum CodingKeys: String, CodingKey {
        case schemaVersion, generatedAt, runDate, sources, sourceFile, sourceFiles, waterbodies, stateStatus
    }

    /// The entry of a state whose data is unavailable, or nil.
    public func outage(state: String) -> StateStatus? {
        stateStatus?.first { $0.state == state && $0.mode == .unavailable }
    }

    /// Every water of an unavailable state with its status, and each spot's,
    /// replaced by an undetermined one that carries the outage, so no
    /// screen, list, widget or alert can show its last records as current.
    func maskingUnavailable() -> Snapshot {
        guard let entries = stateStatus, entries.contains(where: { $0.mode == .unavailable }) else { return self }
        let masked = waterbodies.map { water -> Waterbody in
            guard let entry = outage(state: water.state), let since = entry.since else { return water }
            let outage = Status.Outage(stateName: Waterbody.stateNames[water.state] ?? water.state,
                                       since: since, lastRead: entry.lastRead, mapUrl: entry.mapUrl)
            let mask = { (status: Status) in
                Status(kind: .undetermined, lastAdvisory: status.lastAdvisory, unavailable: outage)
            }
            return Waterbody(id: water.id, state: water.state, name: water.name, countyText: water.countyText,
                             counties: water.counties, center: water.center, status: mask(water.status),
                             sites: water.sites.map { Site(id: $0.id, landmark: $0.landmark, lat: $0.lat, lon: $0.lon, status: mask($0.status)) },
                             records: water.records, satellite: water.satellite)
        }
        return Snapshot(schemaVersion: schemaVersion, generatedAt: generatedAt, runDate: runDate, sources: sources,
                        sourceFile: sourceFile, sourceFiles: sourceFiles, waterbodies: masked, stateStatus: stateStatus)
    }
}

/// One state's data mode, as the pipeline wrote it.
public struct StateStatus: Codable, Equatable, Sendable {
    public enum Mode: String, Codable, Sendable {
        case live
        case staleDated = "stale_dated"
        case unavailable
    }

    public let state: String
    public let source: String
    public let mode: Mode
    public let lastRead: PlainDate?
    public let since: PlainDate?
    public let reason: String?
    public let mapUrl: String
}

/// Official advisories decide a status; satellite estimates never do.
public enum RecordKind: String, Codable, Sendable {
    case officialAdvisory = "official_advisory"
    case satelliteEstimate = "satellite_estimate"
}

/// One data source, with its license, attribution, required disclaimer and
/// how it records the end of an advisory. Every record names its source.
public struct DataSource: Codable, Equatable, Sendable {
    public let id: String
    public let state: String
    public let agency: String
    public let program: String
    public let datasetUrl: String
    public let officialMapUrl: String
    public let license: String
    public let rights: String
    public let attribution: String
    public let contact: String
    public let recordKind: RecordKind
    /// `explicit_record`, `explicit_field`, `rolling_window` or `none_recorded`.
    public let liftSemantics: String
    public let liftExplanation: String
    /// Shown verbatim wherever this source's data is shown, when not empty.
    public let requiredDisclaimer: String
    public let revocable: Bool
    public let revocationClause: String
}

public struct SourceFile: Codable, Equatable, Sendable {
    public let source: String
    public let fileName: String
    public let fileDate: PlainDate
    public let fetchedAt: String
    public let newestRecordDate: PlainDate?
}

public struct Coordinate: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double
}

/// The advisory levels on the Caution, Warning, Danger scale, plus the
/// state's other advisory sign types.
public enum AdvisoryTier: String, Codable, Sendable, CaseIterable {
    case danger
    case warning
    case caution
    case otherAdvisory = "other_advisory"

    public var rank: Int {
        switch self {
        case .danger: 4
        case .warning: 3
        case .caution: 2
        case .otherAdvisory: 1
        }
    }
}

/// A record's tier: an advisory tier, the state's explicit "None", or a
/// record that decides nothing.
public enum RecordTier: String, Codable, Sendable {
    case danger, warning, caution
    case otherAdvisory = "other_advisory"
    case noAdvisory = "no_advisory"
    case notClassified = "not_classified"
    case unknown

    public var isAdvisory: Bool { [.danger, .warning, .caution, .otherAdvisory].contains(self) }
}

public struct Status: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case advisory
        case noAdvisoryRecorded = "no_advisory_recorded"
        case undetermined
    }

    public enum LiftKind: String, Codable, Sendable {
        case noAdvisoryRecord = "no_advisory_record"
        case dissipated
        case endDate = "end_date"
    }

    public let kind: Kind
    public let tier: AdvisoryTier?
    public let level: String?
    public let posted: PlainDate?
    public let plannedEnd: PlainDate?
    public let liftKind: LiftKind?
    public let liftDate: PlainDate?
    public let lastAdvisory: PlainDate?
    public let sitesWithAdvisory: Int
    /// Set by the decoder, never read from the file, when this water's state
    /// is in its "data unavailable" mode (DECISIONS 0024). The status then
    /// reads as undetermined, says nothing current, and never alerts.
    public private(set) var unavailable: Outage? = nil

    /// Why a state's status is not shown, and where to look instead.
    public struct Outage: Equatable, Sendable {
        public let stateName: String
        public let since: PlainDate
        public let lastRead: PlainDate?
        public let mapUrl: String

        public init(stateName: String, since: PlainDate, lastRead: PlainDate?, mapUrl: String) {
            self.stateName = stateName
            self.since = since
            self.lastRead = lastRead
            self.mapUrl = mapUrl
        }
    }

    enum CodingKeys: String, CodingKey {
        case kind, tier, level, posted, plannedEnd, liftKind, liftDate, lastAdvisory, sitesWithAdvisory
    }

    public init(kind: Kind, tier: AdvisoryTier? = nil, level: String? = nil, posted: PlainDate? = nil,
                plannedEnd: PlainDate? = nil, liftKind: LiftKind? = nil, liftDate: PlainDate? = nil,
                lastAdvisory: PlainDate? = nil, sitesWithAdvisory: Int = 0, unavailable: Outage? = nil) {
        self.unavailable = unavailable
        self.kind = kind
        self.tier = tier
        self.level = level
        self.posted = posted
        self.plannedEnd = plannedEnd
        self.liftKind = liftKind
        self.liftDate = liftDate
        self.lastAdvisory = lastAdvisory
        self.sitesWithAdvisory = sitesWithAdvisory
    }
}

public struct Site: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let landmark: String
    public let lat: Double?
    public let lon: Double?
    public let status: Status
}

public struct AdvisoryRecord: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let site: String
    public let date: PlainDate
    public let level: String
    public let tier: RecordTier
    public let explicitNoAdvisory: Bool
    public let endDate: PlainDate?
    public let detail: String
    public let source: String
    public let recordKind: RecordKind
    public let removedFromSource: PlainDate?
}

/// EPA CyAN's weekly satellite estimate for a large lake. Never an advisory,
/// never the end of one; it measures abundance, not toxins.
public struct SatelliteEstimate: Codable, Equatable, Sendable {
    public struct Reading: Codable, Equatable, Sendable {
        public let weekEnd: PlainDate
        public let cellsPerMl: Int
        public let maxCellsPerMl: Int?
        public let validCells: Int
    }

    public let source: String
    public let recordKind: RecordKind
    public let cyanName: String
    public let cyanObjectid: Int
    public let areaKm2: Double
    public let fetchedAt: String
    /// Newest first. Empty means no usable week, never zero.
    public let readings: [Reading]
}

public struct Waterbody: Codable, Equatable, Sendable, Identifiable {
    public typealias ID = String
    public let id: ID
    public let state: String
    public let name: String
    public let countyText: String
    public let counties: [String]
    public let center: Coordinate?
    public let status: Status
    public let sites: [Site]
    public let records: [AdvisoryRecord]
    public let satellite: SatelliteEstimate?

    public init(id: ID, state: String, name: String, countyText: String, counties: [String], center: Coordinate?,
                status: Status, sites: [Site], records: [AdvisoryRecord], satellite: SatelliteEstimate? = nil) {
        self.id = id
        self.state = state
        self.name = name
        self.countyText = countyText
        self.counties = counties
        self.center = center
        self.status = status
        self.sites = sites
        self.records = records
        self.satellite = satellite
    }

    /// "Alameda County", "Calaveras and Tuolumne County", or the source
    /// text when it names no California county.
    public var countyLabel: String {
        if !counties.isEmpty { return counties.joined(separator: " and ") + " County" }
        if !countyText.isEmpty { return countyText }
        // Missouri's layer names no county; California's rows sometimes omit it.
        return state == "CA" ? "County not recorded" : (Self.stateNames[state] ?? state)
    }

    public func site(id: String) -> Site? { sites.first { $0.id == id } }

    public static let stateNames = ["CA": "California", "MO": "Missouri"]
}
