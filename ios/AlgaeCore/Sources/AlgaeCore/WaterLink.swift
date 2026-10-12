import Foundation

/// `algaealerts://water/<id>` opens a lake; `algaealerts://unlock` opens the
/// purchase screen. Opening a link makes no network request.
public enum WaterLink {
    public static let scheme = "algaealerts"
    public static let notificationWaterKey = "waterID"

    public static func url(for id: Waterbody.ID) -> URL {
        URL(string: "\(scheme)://water/\(id)")!
    }

    public static let unlockURL = URL(string: "\(scheme)://unlock")!

    public enum Destination: Equatable {
        case water(Waterbody.ID)
        case unlock
    }

    public static func destination(for url: URL) -> Destination? {
        guard url.scheme == scheme else { return nil }
        switch url.host {
        case "water":
            let id = url.pathComponents.dropFirst().first ?? ""
            let valid = !id.isEmpty && id.allSatisfy { $0.isLowercase || $0.isNumber || $0 == "-" }
            return valid ? .water(id) : nil
        case "unlock":
            return .unlock
        default:
            return nil
        }
    }

    public static func waterID(fromNotificationUserInfo info: [AnyHashable: Any]) -> Waterbody.ID? {
        info[notificationWaterKey] as? String
    }
}
