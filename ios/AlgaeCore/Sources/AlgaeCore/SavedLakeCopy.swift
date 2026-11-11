import Foundation

/// What Favorites says about a saved lake the data on this iPhone does not
/// have (docs/DECISIONS.md 0039).
///
/// The app saves only a lake's id, so a missing lake has no name or status
/// to show. The old line, "No longer in the state's current file.", claimed
/// something the phone cannot know: with no data file it was shown for every
/// favorite, and a lake can also leave Lake Notice's data because a state's
/// layer dropped it or a state is switched off. This names what is missing
/// (Lake Notice's data, dated), never the state's file, and says the gap is
/// not a finding of no advisory.
public enum SavedLakeCopy {
    public static let title = "A saved lake"

    public static let notAFinding = "That is not a finding of no advisory."

    public static func detail(id: Waterbody.ID, snapshot: Snapshot?) -> String {
        guard let snapshot else {
            return "Lake Notice has no lake data on this iPhone yet, so it can't show this lake's status. \(notAFinding)"
        }
        let date = snapshot.runDate.label
        if let state = state(of: id), let name = Waterbody.stateNames[state],
           !snapshot.waterbodies.contains(where: { $0.state == state }) {
            return "Lake Notice's data dated \(date) has no \(name) lakes, so it can't show this lake's status. \(notAFinding)"
        }
        return "This lake is not in Lake Notice's data dated \(date), so it can't show its status. \(notAFinding)"
    }

    /// The state code a water id starts with ("mo-..." is Missouri), when it
    /// names a state this build knows; otherwise nil, and nothing is guessed.
    static func state(of id: Waterbody.ID) -> String? {
        guard let prefix = id.split(separator: "-", maxSplits: 1).first else { return nil }
        let code = prefix.uppercased()
        return Waterbody.stateNames[code] == nil ? nil : code
    }
}
