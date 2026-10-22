import Foundation

/// When the app last checked for a new snapshot, and the server's ETag.
public struct SnapshotMeta: Codable, Equatable, Sendable {
    public var lastAttempt: Date?
    public var lastSuccess: Date?
    public var lastAttemptFailed: Bool
    public var etag: String?

    public init(lastAttempt: Date? = nil, lastSuccess: Date? = nil, lastAttemptFailed: Bool = false, etag: String? = nil) {
        self.lastAttempt = lastAttempt
        self.lastSuccess = lastSuccess
        self.lastAttemptFailed = lastAttemptFailed
        self.etag = etag
    }
}

/// The snapshot on this phone: the last one downloaded, or the copy that
/// ships inside the app, whichever is newer by its source file date.
public struct SnapshotStore: Sendable {
    public let layout: AppStorageLayout
    public let bundled: URL?

    public init(layout: AppStorageLayout, bundled: URL?) {
        self.layout = layout
        self.bundled = bundled
    }

    public func load() -> Snapshot? {
        let saved = (try? Data(contentsOf: layout.snapshotFile)).flatMap { try? SnapshotDecoder.decode($0) }
        let shipped = bundled.flatMap { try? Data(contentsOf: $0) }.flatMap { try? SnapshotDecoder.decode($0) }
        switch (saved, shipped) {
        case let (s?, b?): return b.sourceFile.fileDate > s.sourceFile.fileDate ? b : s
        case let (s?, nil): return s
        case let (nil, b?): return b
        default: return nil
        }
    }

    public func save(_ data: Data) throws {
        try data.write(to: layout.snapshotFile, options: .atomic)
    }

    public func meta() -> SnapshotMeta {
        ((try? JSONFileStore<SnapshotMeta>(url: layout.snapshotMetaFile).load()) ?? nil) ?? SnapshotMeta()
    }

    public func save(meta: SnapshotMeta) throws {
        try JSONFileStore(url: layout.snapshotMetaFile).save(meta)
    }
}

public enum SnapshotEndpoint {
    /// Where the pipeline publishes the snapshot: `snapshot/v1.json` under the
    /// site's own domain (docs/DECISIONS.md 0013). The domain is
    /// `SITE_DOMAIN` in pipeline/src/caalgae/site.py and a test fails if the
    /// two drift. Until the site is live a check fails politely and the app
    /// keeps the copy it ships with. Shipped builds keep this URL.
    public static let url = URL(string: "https://lakenotice.com/snapshot/v1.json")!
    public static let siteURL = URL(string: "https://lakenotice.com/")!
}

public enum RefreshOutcome: Equatable, Sendable {
    case updated(Snapshot)
    case notModified
    case failed(String)
}

/// The app's one network request: a conditional GET of the snapshot. It
/// carries no identifier and nothing about the person.
public struct SnapshotRefresher: Sendable {
    public let session: URLSession
    public let store: SnapshotStore
    public let url: URL

    public init(session: URLSession = .shared, store: SnapshotStore, url: URL = SnapshotEndpoint.url) {
        self.session = session
        self.store = store
        self.url = url
    }

    public func refresh(now: Date = Date()) async -> RefreshOutcome {
        var meta = store.meta()
        meta.lastAttempt = now
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        if let etag = meta.etag { request.setValue(etag, forHTTPHeaderField: "If-None-Match") }
        let outcome: RefreshOutcome
        do {
            let (data, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            switch http?.statusCode {
            case 304:
                outcome = .notModified
            case 200:
                let snapshot = try SnapshotDecoder.decode(data)
                if let current = store.load(), current.sourceFile.fileDate > snapshot.sourceFile.fileDate {
                    outcome = .failed("the server's file is older than the one on this phone")
                } else {
                    try store.save(data)
                    meta.etag = http?.value(forHTTPHeaderField: "ETag")
                    outcome = .updated(snapshot)
                }
            default:
                outcome = .failed("HTTP \(http?.statusCode ?? 0)")
            }
        } catch {
            outcome = .failed(String(describing: error))
        }
        if case .failed = outcome { meta.lastAttemptFailed = true } else {
            meta.lastAttemptFailed = false
            meta.lastSuccess = now
        }
        try? store.save(meta: meta)
        return outcome
    }
}

/// At most one foreground check every 6 hours, or 30 minutes after a
/// failure. The source is republished about daily.
public enum RefreshThrottle {
    public static func isDue(_ meta: SnapshotMeta, now: Date = Date()) -> Bool {
        guard let last = meta.lastAttempt else { return true }
        let wait: TimeInterval = meta.lastAttemptFailed ? 30 * 60 : 6 * 60 * 60
        return now.timeIntervalSince(last) >= wait
    }
}
