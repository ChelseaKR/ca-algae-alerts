import Foundation
import XCTest
@testable import AlgaeCore

/// The purchase is named for what it adds, not Trout Truck's "Full Access",
/// and the product id never changes (DECISIONS 0030).
final class PurchaseNameTests: XCTestCase {
    private func storeKitProduct() throws -> [String: Any] {
        let ios = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
        let data = try Data(contentsOf: ios.appendingPathComponent("AlgaeAlerts/Configuration.storekit"))
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let products = try XCTUnwrap(root["products"] as? [[String: Any]])
        XCTAssertEqual(products.count, 1)
        return try XCTUnwrap(products.first)
    }

    func testTheStoreKitProductCarriesTheNewNameAndTheOldId() throws {
        let product = try storeKitProduct()
        XCTAssertEqual(product["productID"] as? String, "net.chelseakr.algaealerts.fullaccess")
        XCTAssertEqual(product["referenceName"] as? String, "Lake Notice Alerts")
        let names = try XCTUnwrap(product["localizations"] as? [[String: Any]]).compactMap { $0["displayName"] as? String }
        XCTAssertEqual(names, [FreeTier.purchaseName])
        XCTAssertLessThanOrEqual(FreeTier.purchaseName.count, 30, "App Store Connect's display-name limit")
        XCTAssertFalse(FreeTier.purchaseName.localizedCaseInsensitiveContains("full access"))
    }
}
