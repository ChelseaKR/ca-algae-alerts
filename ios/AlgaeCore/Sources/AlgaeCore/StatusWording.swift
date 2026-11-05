import Foundation

/// Every sentence the app uses to describe a status. Mirrors
/// `pipeline/src/caalgae/wording.py` so the site and the app say the same
/// thing; `StatusWordingTests` pins the strings.
///
/// The rules: never say a water is safe; an advisory reads "last posted
/// <date>, no all-clear recorded" until the state records an end; every
/// status carries its date; speak to everyone, with dogs in their own
/// labeled section; no fear-led copy.
public enum StatusWording {
    public static func levelName(_ status: Status) -> String {
        switch status.tier {
        case .danger: "Danger advisory"
        case .warning: "Warning advisory"
        case .caution: "Caution advisory"
        case .otherAdvisory, .none: status.level.flatMap { $0.isEmpty ? nil : $0 } ?? "Advisory"
        }
    }

    public static func headline(_ status: Status) -> String {
        switch status.kind {
        case .advisory:
            let posted = status.posted?.label ?? "on an unrecorded date"
            return "\(levelName(status)), last posted \(posted). No all-clear recorded."
        case .noAdvisoryRecorded:
            let date = status.liftDate?.label ?? "an unrecorded date"
            if status.liftKind == .endDate {
                return "The state recorded an end date of \(date)."
            }
            if status.liftKind == .dissipated {
                return "The state recorded the bloom as dissipated on \(date)."
            }
            return "The state's latest record, from \(date), recommends no advisory."
        case .undetermined:
            return "Reports on file, with no advisory level the state has classified."
        }
    }

    /// A short form for list rows and the widget.
    public static func shortLine(_ status: Status) -> String {
        switch status.kind {
        case .advisory:
            return "\(levelName(status)) · posted \(status.posted?.label ?? "date not recorded")"
        case .noAdvisoryRecorded:
            let what = status.liftKind == .dissipated ? "Dissipated" : (status.liftKind == .endDate ? "End date recorded" : "No advisory in latest record")
            return "\(what) · \(status.liftDate?.label ?? "date not recorded")"
        case .undetermined:
            return "Reports on file, level not classified"
        }
    }

    public static func caveat(_ status: Status) -> String {
        if status.kind == .advisory {
            return "Reporting is voluntary, so the state may not have recorded an end even if conditions changed. Check posted signs and the official map."
        }
        return "That reflects what the state knew on that date. It is not a finding that the water is safe now: blooms can return within days, and many are never reported."
    }

    // Paraphrased from the state's own posted-sign wording, the same as
    // `LEVEL_GUIDANCE` in wording.py (its comment quotes each source in
    // full). Sources, read 2026-11-05:
    // California HAB program, https://mywaterquality.ca.gov/habs/resources/signage.html
    //   CAUTION and WARNING: "Do not let pets and other animals go into or
    //   drink the water, or eat scum on the shore." WARNING and DANGER: "Do
    //   not use this water for drinking or cooking. Boiling or filtering will
    //   not make the water safe." CAUTION and WARNING: "For fish caught here,
    //   throw away guts and clean fillets with tap water or bottled water
    //   before cooking." DANGER: "Do not eat fish or shellfish from this water."
    // California toxic algal mat signs, https://mywaterquality.ca.gov/habs/docs/toxic-algal-mat-signs.pdf
    //   "Do NOT let dogs eat algal mats or drink from the water." "Do NOT let
    //   children or adults touch, eat, or swallow any algal mats."
    // Missouri DNR, https://dnr.mo.gov/water/hows-water/pollutants-sources/harmful-algal-blooms-habs/animal-health
    //   "Do not let pets drink or play in the water or roll in or eat the
    //   algae, even if dried." .../human-health: "we recommend you do not eat
    //   fish from affected areas for two weeks after the bloom visually
    //   dissipates."
    public static let waterUse = "Do not drink this water or cook with it; boiling or filtering does not make it safe."
    static let fish = "For fish caught here, throw away the guts and clean fillets with tap or bottled water before cooking. Do not eat shellfish from this water."

    public static func guidance(_ tier: AdvisoryTier) -> String {
        switch tier {
        case .caution:
            "Algae that can make toxins may be present. Keep people, children and pets away from algae and scum in the water and on the shore. Do not let pets or other animals go into or drink the water, or eat scum on the shore. \(waterUse) \(fish)"
        case .warning:
            "Toxins may be at levels that can harm people and animals. Do not swim or let children in the water, and stay away from scum and cloudy or discolored water. Do not let pets or other animals go into or drink the water, or eat scum on the shore. \(waterUse) \(fish)"
        case .danger:
            "Toxins may be at levels that can seriously harm people and animals. Stay out of the water and keep children away from the water and the shore. Do not let pets or other animals go into or drink the water, or go near the scum. \(waterUse) Do not eat fish or shellfish from this water."
        case .otherAdvisory:
            "The state recorded an advisory of a type outside the Caution, Warning and Danger levels. Read the sign posted at the water. \(waterUse)"
        }
    }

    /// The state's toxic algal mat signs share the other-advisory tier.
    public static let algalMatGuidance = "Toxic algal mats may be present. Mats can be attached to the bottom, floating, or washed up on shore. Do not let dogs eat algal mats or drink from the water, and do not let children or adults touch, eat or swallow any algal mats. \(waterUse) Call a doctor or veterinarian if you or your pet get sick after contact with algae."

    public static func isAlgalMat(_ level: String?) -> Bool {
        (level ?? "").lowercased().contains("algal mat")
    }

    /// For a state whose levels are not California's: no level-by-level
    /// summary is invented.
    public static let genericGuidance = "The state recorded an advisory here. Read the state's notice and any sign posted at the water, and keep people, children and pets out of discolored or scummy water."

    /// Missouri's advisories have no levels: one summary of the DNR's own guidance.
    public static let stateGuidance: [String: String] = [
        "MO": "\(genericGuidance) Do not let pets drink or play in the water or roll in or eat the algae, even if dried. \(waterUse) The department advises not eating fish from the area for two weeks after the bloom visually dissipates; if you do, remove all fat, skin and organs and cook the fish thoroughly.",
    ]

    /// What this level asks, for a water in its own state's terms.
    public static func guidance(for water: Waterbody) -> String? {
        guard let tier = water.status.tier else { return nil }
        guard water.state == "CA" else { return stateGuidance[water.state] ?? genericGuidance }
        if tier == .otherAdvisory, isAlgalMat(water.status.level) { return algalMatGuidance }
        return guidance(tier)
    }

    public static let satelliteExplainer = "This is a satellite estimate from the U.S. EPA's Cyanobacteria Assessment Network, not an advisory. It estimates how much cyanobacteria is in the water near the lake's center, not whether toxins are present: a high number does not mean toxins, and a low one does not mean there are none. It covers lakes of about 1 square kilometer and larger, so small ponds, dog parks and most rivers are not covered, and clouds can hide a lake for weeks. It never changes the advisory status above."

    /// `about 550,000 cells/mL`, rounded to two significant figures.
    public static func cellsLabel(_ cells: Int) -> String {
        guard cells > 0 else { return "below what the satellite can detect" }
        let magnitude = pow(10.0, floor(log10(Double(cells))) - 1)
        let rounded = Int((Double(cells) / magnitude).rounded() * magnitude)
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = Locale(identifier: "en_US")
        return "about \(formatter.string(from: NSNumber(value: rounded)) ?? String(rounded)) cells/mL"
    }

    public static let dogAdvice = "Dogs are more exposed than people: they swim through scum, drink the water and lick algae off their fur. Where an advisory is on file, keep your dog out of the water and away from scum on the shore. If your dog does go in, rinse it with clean water and do not let it lick its coat. Call a veterinarian at once if your dog vomits, drools, stumbles or has a seizure after being near the water."

    /// What a person should do after contact, paraphrased from the CDC and the
    /// California Water Boards' advisory signs. Mirrors `HUMAN_ADVICE`.
    public static let humanAdvice = "If you or a child go in water that may have toxic algae, shower or rinse off with tap water right away. If anyone gets sick afterward, call a doctor or Poison Control at 1-800-222-1222."

    /// Mirrors `NOT_MEDICAL_ADVICE`.
    public static let notMedicalAdvice = "Lake Notice republishes state records for information only. It is not medical advice, and records can be late or wrong. In an emergency, call 911. For a possible poisoning, call Poison Control at 1-800-222-1222."

    public static func dogAnswer(name: String, status: Status) -> String {
        switch status.kind {
        case .advisory:
            return "The state has an advisory on file for \(name) (\(levelName(status))), last posted \(status.posted?.label ?? "on an unrecorded date"), and no all-clear recorded. Keep your dog out of the water and away from scum on the shore until the state records an end."
        case .noAdvisoryRecorded:
            return "\(headline(status)) For \(name), that is not the same as an all-clear for today. Look at the water before your dog goes in: keep it out of green, blue-green or scummy water and away from mats on the shore."
        case .undetermined:
            return "The state has reports on file for \(name) but has not classified an advisory level, so the records cannot answer this. Keep your dog out of discolored or scummy water."
        }
    }

    /// The text a record row shows for the state's own level.
    public static func recordLevel(_ record: AdvisoryRecord) -> String {
        record.level.isEmpty ? "Blank in the state's file" : record.level
    }
}
