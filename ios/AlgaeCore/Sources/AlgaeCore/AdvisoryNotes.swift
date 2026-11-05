import Foundation

/// The lines a water's status box carries under its headline, the same
/// sentences as `newer_posting`, `older_higher` and `age_note` in
/// `pipeline/src/caalgae/wording.py` (docs/DECISIONS.md 0017).
///
/// The headline itself comes from the snapshot: the pipeline picks the
/// highest level posted in the 12 months before the state's file date, at
/// that level's own last posted date, or the newest posting when nothing was
/// posted in that window. Reports at the same coordinates, or with the same
/// landmark within 25 m (0022), are already one reported spot in the
/// snapshot. These lines only read the snapshot's spots
/// and records; they never end an advisory (0002).
/// `AdvisoryParityTests` checks them against the website's sentences for
/// Lake Elsinore's real records.
extension StatusWording {
    /// An advisory last posted longer ago than this, counted to the state's
    /// file date, says how old it is (`STALE_DAYS` in wording.py).
    public static let staleDays = 90

    /// Shown when more than one spot has an advisory: how the headline's
    /// posting was chosen.
    public static let headlineRule = "The headline shows the highest level posted in the 12 months before the state's data, or the newest posting if none was. Each spot's latest status is listed under Reported spots below."

    /// A newer posting at a lower level than the headline's, or nil when
    /// the headline's posting is the newest.
    public static func newerPosting(_ water: Waterbody) -> String? {
        guard water.status.kind == .advisory, let newest = WaterSearch.newestPosted(water),
              newest != water.status.posted else { return nil }
        let at = advisorySites(water).filter { $0.posted == newest }
        guard let top = firstMax(at, by: rank) else { return nil }
        return "The newest advisory posting here is lower: \(levelName(top)), posted \(newest.label) at \(spots(at.count)). No all-clear recorded."
    }

    /// A higher advisory than the headline's, posted before the 12-month
    /// window and never lifted, or nil. It stays in view; it no longer leads.
    public static func olderHigher(_ water: Waterbody) -> String? {
        guard water.status.kind == .advisory else { return nil }
        let headlineRank = rank(water.status)
        let higher = advisorySites(water).filter { $0.posted != nil && rank($0) > headlineRank }
        guard let topRank = higher.map(rank).max() else { return nil }
        let atTop = higher.filter { rank($0) == topRank }
        guard let first = atTop.first, let latest = atTop.compactMap(\.posted).max() else { return nil }
        return "An older, higher advisory is also on file: \(levelName(first)), last posted \(latest.label) at \(spots(atTop.count)). No all-clear recorded."
    }

    /// How old the headline's posting is, when it was posted more than
    /// `staleDays` before the state's file date, and the date of the state's
    /// newest record of any kind for the water when that is newer. It says
    /// how old the record is, never that the advisory has ended.
    public static func ageNote(_ water: Waterbody, fileDate: PlainDate?) -> String? {
        guard water.status.kind == .advisory, let fileDate, let posted = water.status.posted else { return nil }
        let days = posted.days(until: fileDate)
        guard days > staleDays else { return nil }
        var line = "That level was last posted \(posted.label), \(age(days: days)) before the state's data dated \(fileDate.label), and the state has not recorded an end to it."
        if let newest = water.records.filter({ $0.removedFromSource == nil }).map(\.date).max(), newest > posted {
            line += " The state's newest record of any kind for \(water.name) is from \(newest.label)."
        }
        return line
    }

    /// The notes in the order the website's water page shows them.
    public static func statusNotes(_ water: Waterbody, fileDate: PlainDate?) -> [String] {
        [newerPosting(water), olderHigher(water), ageNote(water, fileDate: fileDate)].compactMap { $0 }
    }

    static func age(days: Int) -> String {
        if days >= 730 { return "more than \(days / 365) years" }
        if days >= 365 { return "more than a year" }
        return "\(days / 30) months"
    }

    private static func advisorySites(_ water: Waterbody) -> [Status] {
        water.sites.map(\.status).filter { $0.kind == .advisory }
    }

    private static func rank(_ status: Status) -> Int { status.tier?.rank ?? 0 }

    private static func spots(_ n: Int) -> String { n == 1 ? "1 reported spot" : "\(n) reported spots" }

    /// The first element with the largest key, as Python's `max` picks.
    private static func firstMax<T>(_ items: [T], by key: (T) -> Int) -> T? {
        items.reduce(nil) { best, item in
            guard let best else { return item }
            return key(item) > key(best) ? item : best
        }
    }
}

extension WaterSearch {
    /// The newest date any of a water's spots had an advisory posted, with
    /// no all-clear since. It can be newer than the headline's date, which
    /// belongs to the headline's level (`newest_posted` in wording.py).
    public static func newestPosted(_ water: Waterbody) -> PlainDate? {
        water.sites.filter { $0.status.kind == .advisory }.compactMap(\.status.posted).max() ?? water.status.posted
    }

    /// Any advisory at the water posted within `days` of `today`, whatever
    /// its level, so a new lower posting is not hidden behind an older,
    /// higher one (`is_recent_water` in wording.py).
    public static func isRecent(_ water: Waterbody, today: PlainDate, days: Int = 30) -> Bool {
        guard let posted = newestPosted(water) else { return false }
        return posted.days(until: today) <= days
    }
}

extension Snapshot {
    /// The date of the file the water's own state's advisories came from.
    public func fileDate(for water: Waterbody) -> PlainDate? {
        guard let source = advisorySource(state: water.state) else { return nil }
        return sourceFiles.first { $0.source == source.id }?.fileDate
    }
}
