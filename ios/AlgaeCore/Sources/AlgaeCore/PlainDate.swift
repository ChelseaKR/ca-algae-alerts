import Foundation

/// A calendar date with no time and no time zone, as the state publishes
/// advisory dates. Decoded from and encoded to `YYYY-MM-DD`.
public struct PlainDate: Codable, Hashable, Comparable, Sendable, CustomStringConvertible {
    public let year: Int
    public let month: Int
    public let day: Int

    public init(year: Int, month: Int, day: Int) {
        self.year = year
        self.month = month
        self.day = day
    }

    public init?(iso: String) {
        let parts = iso.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3, (1...12).contains(parts[1]), (1...31).contains(parts[2]) else { return nil }
        self.init(year: parts[0], month: parts[1], day: parts[2])
    }

    public init(from decoder: Decoder) throws {
        let text = try decoder.singleValueContainer().decode(String.self)
        guard let date = PlainDate(iso: text) else {
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "not a YYYY-MM-DD date: \(text)"))
        }
        self = date
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(iso)
    }

    public var iso: String { String(format: "%04d-%02d-%02d", year, month, day) }
    public var description: String { iso }

    public static func < (a: PlainDate, b: PlainDate) -> Bool {
        (a.year, a.month, a.day) < (b.year, b.month, b.day)
    }

    private static let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    /// `Oct 9, 2026`, the same form the website uses.
    public var label: String { "\(Self.months[month - 1]) \(day), \(year)" }

    /// Today in Los Angeles, the state's own calendar.
    public static func today(now: Date = Date()) -> PlainDate {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/Los_Angeles") ?? .current
        let c = calendar.dateComponents([.year, .month, .day], from: now)
        return PlainDate(year: c.year ?? 1970, month: c.month ?? 1, day: c.day ?? 1)
    }

    /// Whole days from `self` to `other` (positive when `other` is later).
    public func days(until other: PlainDate) -> Int {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC") ?? .current
        let a = calendar.date(from: DateComponents(year: year, month: month, day: day)) ?? .distantPast
        let b = calendar.date(from: DateComponents(year: other.year, month: other.month, day: other.day)) ?? .distantPast
        return calendar.dateComponents([.day], from: a, to: b).day ?? 0
    }
}
