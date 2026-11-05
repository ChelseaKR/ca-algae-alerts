import Foundation

public enum WaterSearch {
    /// Case- and accent-insensitive match on the name and the county.
    public static func filter(_ waters: [Waterbody], query: String) -> [Waterbody] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return waters }
        let options: String.CompareOptions = [.caseInsensitive, .diacriticInsensitive]
        return waters.filter {
            $0.name.range(of: q, options: options) != nil || $0.countyLabel.range(of: q, options: options) != nil
        }
    }

    /// Waters whose latest record is an advisory, newest posting at any
    /// level first (as the website orders them, decision 0017), then by
    /// the headline's level.
    public static func advisories(_ waters: [Waterbody]) -> [Waterbody] {
        waters.filter { $0.status.kind == .advisory }.sorted { a, b in
            let pa = newestPosted(a) ?? PlainDate(year: 0, month: 1, day: 1)
            let pb = newestPosted(b) ?? PlainDate(year: 0, month: 1, day: 1)
            if pa != pb { return pa > pb }
            let ra = a.status.tier?.rank ?? 0, rb = b.status.tier?.rank ?? 0
            if ra != rb { return ra > rb }
            return a.name < b.name
        }
    }

    public static func alphabetical(_ waters: [Waterbody]) -> [Waterbody] {
        waters.sorted { ($0.name.lowercased(), $0.id) < ($1.name.lowercased(), $1.id) }
    }

    /// Posted within `days` of `today`.
    public static func isRecent(_ status: Status, today: PlainDate, days: Int = 30) -> Bool {
        guard let posted = status.posted else { return false }
        return posted.days(until: today) <= days
    }
}
