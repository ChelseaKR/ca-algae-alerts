// swift-tools-version: 5.10
// AlgaeCore: the app's data layer. Foundation only, no third-party
// dependencies. Builds and tests on macOS with `swift test`, no simulator.
//
// `type: .dynamic`: the app's unit tests run hosted inside the app, and a
// static library linked into both the app and the hosted test bundle fails
// at link time (measured on Trout Truck's PlantingCore, same shape).
import PackageDescription

let package = Package(
    name: "AlgaeCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "AlgaeCore", type: .dynamic, targets: ["AlgaeCore"]),
    ],
    targets: [
        .target(name: "AlgaeCore", path: "Sources/AlgaeCore"),
        .testTarget(
            name: "AlgaeCoreTests",
            dependencies: ["AlgaeCore"],
            path: "Tests/AlgaeCoreTests",
            resources: [.copy("Fixtures")]
        ),
    ]
)
