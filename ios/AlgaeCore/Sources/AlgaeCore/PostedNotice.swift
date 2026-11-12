import Foundation

/// The posted-sign band the website draws over a status (docs/DESIGN.md,
/// DECISIONS 0035), as data the app can draw and test. The app shows the
/// same band (DECISIONS 0036).
///
/// Only an advisory gets a sign color and a word for its level. California's
/// three levels also get one to three rank marks, so the level reads from
/// the words and from a shape, never from color alone. Anything that is not
/// an advisory says "Latest state record" on a neutral band: never a word
/// or a color that reads as an all-clear.
public struct NoticeBand: Equatable, Sendable {
    public enum Paint: String, Sendable, CaseIterable {
        case caution, warning, danger
        /// A state's own sign type off the three-level scale (Missouri's
        /// levels, California's algal-mat signs). Slate, no rank marks.
        case otherAdvisory
        /// Not an advisory. Neutral, drawn with a dashed edge.
        case record
    }

    public let paint: Paint
    /// The band's words, as the site's band shows them before uppercasing.
    public let words: String
    /// 1 to 3 on California's scale, nil off it.
    public let rank: Int?

    public static let rankCount = 3
    public static let recordWords = "Latest state record"

    public init(_ status: Status) {
        guard status.kind == .advisory else {
            paint = .record
            words = Self.recordWords
            rank = nil
            return
        }
        words = StatusWording.levelName(status)
        switch status.tier {
        case .caution: paint = .caution; rank = 1
        case .warning: paint = .warning; rank = 2
        case .danger: paint = .danger; rank = 3
        case .otherAdvisory, .none: paint = .otherAdvisory; rank = nil
        }
    }

    /// The record table's level, as a band: the same paint and rank as a
    /// status with that tier, and no level color for a record that is not an
    /// advisory.
    public init(record: AdvisoryRecord) {
        let tier: AdvisoryTier? = switch record.tier {
        case .danger: .danger
        case .warning: .warning
        case .caution: .caution
        case .otherAdvisory: .otherAdvisory
        case .noAdvisory, .notClassified, .unknown: nil
        }
        if let tier {
            self.init(Status(kind: .advisory, tier: tier, level: record.level))
        } else {
            self.init(Status(kind: .undetermined))
        }
    }

    public var isAdvisory: Bool { paint != .record }

    /// Danger's notice has the heavier edge, as on the site.
    public var heavyEdge: Bool { paint == .danger }

    /// What VoiceOver reads for the band: the words, then the rank in words.
    public var spoken: String {
        if let rank { return "\(words) sign, \(rank) of \(Self.rankCount) marks" }
        if paint == .record { return "\(words), not an advisory" }
        return "\(words) sign"
    }
}

/// Sharing a lake sends its page on the website: a link anyone can open,
/// with no app needed and nothing about the sender attached.
public enum LakeShare {
    public static func url(for id: Waterbody.ID) -> URL {
        SnapshotEndpoint.siteURL.appendingPathComponent("water/\(id)/")
    }

    public static func subject(_ water: Waterbody) -> String {
        "\(water.name) on Lake Notice"
    }

    /// Says what the page holds, never what the water is like.
    public static func message(_ water: Waterbody) -> String {
        "The state's toxic algae advisory records for \(water.name), each with its date. Check posted signs before you go."
    }
}

/// When the app may ask for an App Store rating (DECISIONS 0036). Apple's
/// rules: ask after the person has done something meaningful, at a pause,
/// never at launch and never from a button. iOS itself caps the prompt at
/// three a year and may show nothing.
///
/// Here the meaningful thing is saving lakes to come back to: the app asks
/// only when someone leaves a lake screen where they just saved a lake,
/// they keep at least `minimumFavorites`, they have opened the app on
/// `minimumDays` different days, and it has not asked in this version.
public struct ReviewAsk: Codable, Equatable, Sendable {
    public static let minimumFavorites = 2
    public static let minimumDays = 3
    /// Only the newest days are kept; the rule only counts to three.
    static let keptDays = 7

    public private(set) var daysOpened: [String]
    public private(set) var askedInVersion: String?

    public init(daysOpened: [String] = [], askedInVersion: String? = nil) {
        self.daysOpened = daysOpened
        self.askedInVersion = askedInVersion
    }

    /// Notes the calendar day the app came to the front. Opening it twice
    /// in a day counts once.
    public mutating func noteOpened(on day: PlainDate) {
        let key = day.description
        guard !daysOpened.contains(key) else { return }
        daysOpened.append(key)
        if daysOpened.count > Self.keptDays { daysOpened.removeFirst(daysOpened.count - Self.keptDays) }
    }

    public func shouldAsk(justSavedALake: Bool, favoriteCount: Int, version: String) -> Bool {
        justSavedALake
            && favoriteCount >= Self.minimumFavorites
            && daysOpened.count >= Self.minimumDays
            && askedInVersion != version
    }

    public mutating func noteAsked(version: String) { askedInVersion = version }
}

/// Words for the screens with nothing to list. Each says what happened and
/// what to do, and none turns a missing record into a finding about a water.
public enum EmptyCopy {
    public static let noDataTitle = "No lake records on this iPhone"
    public static let noDataMessage = "Lake Notice could not read the state's advisory records. Try again, or check the official state map."
    public static let offlineTitle = "This iPhone is offline"
    public static let offlineNoDataMessage = "Lake Notice needs a connection once to download the state's advisory records. Connect and try again."
    public static func offlineBanner(fileDate: PlainDate) -> String {
        "This iPhone is offline. Showing the copy already on it, from the data file dated \(fileDate.label)."
    }

    public static func noMatchTitle(_ query: String) -> String {
        "No lake matches \u{201C}\(query.trimmingCharacters(in: .whitespaces))\u{201D}"
    }
    public static let noMatchMessage = "Try part of the name, or the county. A lake missing here has no advisory record Lake Notice could read. That is not a finding about the water: most lakes are never tested."

    public static let noFavoritesTitle = "No saved lakes yet"
    public static let noFavoritesMessage = "Open a lake and tap the star to keep it here. Saved lakes are the ones alerts can watch."

    public static let goneTitle = "Not in the current data"
    public static let goneMessage = "This lake is not in the state's current file. Its favorite and alert settings are kept."
}

/// The support email, with a subject that says which app it is about.
public enum SupportContact {
    public static let address = "chelsea@chelseakr.com"

    /// With no version on hand the subject leaves it out rather than
    /// inventing one.
    public static func mailURL(version: String?) -> URL {
        var parts = URLComponents()
        parts.scheme = "mailto"
        parts.path = address
        let subject = ["Lake Notice for iPhone", version].compactMap { $0 }.joined(separator: " ")
        parts.queryItems = [URLQueryItem(name: "subject", value: subject)]
        return parts.url!
    }
}
