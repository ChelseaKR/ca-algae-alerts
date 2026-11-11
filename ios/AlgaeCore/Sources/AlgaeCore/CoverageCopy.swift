import Foundation

/// One state the snapshot on this phone actually carries waters for, and the
/// year of its oldest advisory record, when it has one.
public struct StateCoverage: Equatable, Sendable {
    public let code: String
    public let name: String
    /// Nil when the state's waters carry no dated record. Never a guessed year.
    public let firstRecordYear: Int?
}

/// Words that depend on what the snapshot holds, built from the snapshot
/// rather than written down here. A state whose source the pipeline lists
/// but whose waters are gone (a retired layer, say) is not named, and the
/// "last 30 days" window counts back from the snapshot's run date, so an old
/// file never reads as "nothing posted lately" (DECISIONS 0031).
public enum CoverageCopy {
    /// States with at least one water in the snapshot, in the order the
    /// snapshot lists their advisory sources (California first).
    public static func states(in snapshot: Snapshot?) -> [StateCoverage] {
        guard let snapshot else { return [] }
        var order: [String] = []
        for source in snapshot.sources where source.recordKind == .officialAdvisory && !order.contains(source.state) {
            order.append(source.state)
        }
        for water in snapshot.waterbodies where !order.contains(water.state) { order.append(water.state) }
        return order.compactMap { code in
            let waters = snapshot.waterbodies.filter { $0.state == code }
            guard !waters.isEmpty else { return nil }
            let first = waters.flatMap(\.records).map(\.date).min()
            return StateCoverage(code: code, name: Waterbody.stateNames[code] ?? code, firstRecordYear: first?.year)
        }
    }

    /// "California", "California and Missouri", "A, B and C".
    public static func joined(_ names: [String]) -> String {
        switch names.count {
        case 0: return ""
        case 1: return names[0]
        default: return names.dropLast().joined(separator: ", ") + " and " + names[names.count - 1]
        }
    }

    /// About's first line.
    public static func aboutSummary(_ snapshot: Snapshot?) -> String {
        let states = states(in: snapshot)
        guard !states.isEmpty else {
            return "Harmful algal bloom advisories that states have recorded for lakes, rivers and shorelines, with each water's history. No advisory data has loaded on this iPhone yet."
        }
        let names = joined(states.map(\.name))
        let since = states.compactMap { s in s.firstRecordYear.map { "\(s.name)'s since \($0)" } }
        let history = since.isEmpty ? "with each water's history" : "with each water's history: \(joined(since))"
        return "Harmful algal bloom advisories that \(names) \(states.count == 1 ? "has" : "have") recorded for lakes, rivers and shorelines, \(history)."
    }

    /// The introduction's first point.
    public static func introSummary(_ snapshot: Snapshot?) -> String {
        let names = joined(states(in: snapshot).map(\.name))
        let who = names.isEmpty ? "State" : names
        return "\(who) advisories for lakes, rivers and shorelines, newest first, with each water's history. For swimmers, families, paddlers, anglers and dog owners."
    }

    // MARK: The advisory list

    /// The window the list calls recent: 30 days back from the run date.
    public static let recentDays = 30

    public static func isRecent(_ water: Waterbody, in snapshot: Snapshot) -> Bool {
        WaterSearch.isRecent(water, today: snapshot.runDate, days: recentDays)
    }

    public static func recentHeader(_ snapshot: Snapshot) -> String {
        "Posted in the 30 days to \(snapshot.runDate.label)"
    }

    public static func recentEmpty(_ snapshot: Snapshot) -> String {
        "None posted in the 30 days to \(snapshot.runDate.label), the date of the data on this iPhone."
    }

    /// The "All lakes" footer. A missing lake is not "no records": it may
    /// have only rows Lake Notice could not read, or a source that dropped it.
    public static func allFooter(_ snapshot: Snapshot) -> String {
        "As of the data dated \(snapshot.runDate.label), a lake missing from this list has no advisory record Lake Notice could read. Most lakes are never tested."
    }
}
