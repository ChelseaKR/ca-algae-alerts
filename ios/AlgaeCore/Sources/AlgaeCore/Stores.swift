import Foundation

/// Where the app keeps its files: Application Support, or the App Group
/// container for what the widget reads.
public struct AppStorageLayout: Sendable {
    public let directory: URL
    public init(directory: URL) { self.directory = directory }

    public var snapshotFile: URL { directory.appendingPathComponent("snapshot.v1.json") }
    public var snapshotMetaFile: URL { directory.appendingPathComponent("snapshot-meta.json") }
    public var favoritesFile: URL { directory.appendingPathComponent("favorites.json") }
    public var baselineFile: URL { directory.appendingPathComponent("alert-baseline.json") }
    public var mutedFile: URL { directory.appendingPathComponent("muted-alerts.json") }
    public var entitlementFile: URL { directory.appendingPathComponent("entitlement.json") }
    public var introFile: URL { directory.appendingPathComponent("intro.json") }

    public static func applicationSupport() throws -> AppStorageLayout {
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let dir = base.appendingPathComponent("AlgaeAlerts", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return AppStorageLayout(directory: dir)
    }
}

/// A Codable value in one JSON file, written atomically.
public struct JSONFileStore<Value: Codable>: Sendable {
    public let url: URL
    public init(url: URL) { self.url = url }

    public func load() throws -> Value? {
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        return try JSONDecoder().decode(Value.self, from: Data(contentsOf: url))
    }

    public func save(_ value: Value) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try encoder.encode(value).write(to: url, options: .atomic)
    }
}

public struct Favorites: Codable, Equatable, Sendable {
    public var ids: [Waterbody.ID]
    public init(ids: [Waterbody.ID] = []) { self.ids = ids }
    public func contains(_ id: Waterbody.ID) -> Bool { ids.contains(id) }
    public mutating func toggle(_ id: Waterbody.ID) {
        if let i = ids.firstIndex(of: id) { ids.remove(at: i) } else { ids.append(id) }
    }
}

public struct PurchaseEntitlement: Codable, Equatable, Sendable {
    public let isPurchased: Bool
    public init(isPurchased: Bool) { self.isPurchased = isPurchased }
}

public struct IntroState: Codable, Equatable, Sendable {
    public var seen: Bool
    public init(seen: Bool) { self.seen = seen }
}

/// Every small store the app keeps. A missing or corrupt file reads as the
/// empty value; for mutes that means a disk problem can only turn alerts
/// back on, never silence a lake the person did not mute.
public struct AppStores: Sendable {
    public let layout: AppStorageLayout
    public init(layout: AppStorageLayout) { self.layout = layout }

    public func favorites() -> Favorites { ((try? JSONFileStore<Favorites>(url: layout.favoritesFile).load()) ?? nil) ?? Favorites() }
    public func save(_ value: Favorites) throws { try JSONFileStore(url: layout.favoritesFile).save(value) }

    public func baseline() -> AlertBaseline { ((try? JSONFileStore<AlertBaseline>(url: layout.baselineFile).load()) ?? nil) ?? AlertBaseline() }
    public func save(_ value: AlertBaseline) throws { try JSONFileStore(url: layout.baselineFile).save(value) }

    public func muted() -> MutedWaters { ((try? JSONFileStore<MutedWaters>(url: layout.mutedFile).load()) ?? nil) ?? MutedWaters() }
    public func save(_ value: MutedWaters) throws { try JSONFileStore(url: layout.mutedFile).save(value) }

    public func entitlement() -> PurchaseEntitlement { ((try? JSONFileStore<PurchaseEntitlement>(url: layout.entitlementFile).load()) ?? nil) ?? PurchaseEntitlement(isPurchased: false) }
    public func save(_ value: PurchaseEntitlement) throws { try JSONFileStore(url: layout.entitlementFile).save(value) }

    public func intro() -> IntroState { ((try? JSONFileStore<IntroState>(url: layout.introFile).load()) ?? nil) ?? IntroState(seen: false) }
    public func save(_ value: IntroState) throws { try JSONFileStore(url: layout.introFile).save(value) }
}

/// The purchase's on-disk cache. StoreKit's `currentEntitlements` is the
/// truth; this only avoids a locked-looking flash at launch.
public struct EntitlementStore: Sendable {
    let stores: AppStores
    public init(layout: AppStorageLayout) { stores = AppStores(layout: layout) }
    public func load() -> PurchaseEntitlement { stores.entitlement() }
    public func save(_ value: PurchaseEntitlement) throws { try stores.save(value) }
}
