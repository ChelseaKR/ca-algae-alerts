import XCTest
@testable import AlgaeCore

final class StubProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) -> (Int, [String: String], Data))?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let (code, headers, data) = Self.handler?(request) ?? (500, [:], Data())
        let response = HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: headers)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

final class RefresherTests: XCTestCase {
    func session() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubProtocol.self]
        return URLSession(configuration: config)
    }

    func testUpdatedThenNotModifiedWithETag() async throws {
        let data = try Fixtures.trapsData()
        let store = SnapshotStore(layout: try Fixtures.tempLayout(), bundled: nil)
        StubProtocol.handler = { request in
            request.value(forHTTPHeaderField: "If-None-Match") == "\"v1\"" ? (304, [:], Data()) : (200, ["ETag": "\"v1\""], data)
        }
        let refresher = SnapshotRefresher(session: session(), store: store)
        guard case .updated(let s) = await refresher.refresh() else { return XCTFail("expected an update") }
        XCTAssertEqual(s.waterbodies.count, 9)
        let second = await refresher.refresh()
        XCTAssertEqual(second, .notModified)
        XCTAssertFalse(store.meta().lastAttemptFailed)
    }

    func testABadFileIsRefusedAndTheCopyOnThePhoneKept() async throws {
        let store = SnapshotStore(layout: try Fixtures.tempLayout(), bundled: nil)
        try store.save(try Fixtures.trapsData())
        StubProtocol.handler = { _ in (200, [:], Data("{\"schema_version\":1}".utf8)) }
        guard case .failed = await SnapshotRefresher(session: session(), store: store).refresh() else { return XCTFail("expected failure") }
        XCTAssertEqual(store.load()?.waterbodies.count, 9)
        XCTAssertTrue(store.meta().lastAttemptFailed)
    }

    func testServerErrorFails() async throws {
        let store = SnapshotStore(layout: try Fixtures.tempLayout(), bundled: nil)
        StubProtocol.handler = { _ in (404, [:], Data()) }
        let outcome = await SnapshotRefresher(session: session(), store: store).refresh()
        XCTAssertEqual(outcome, .failed("HTTP 404"))
    }
}
