// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "DispatchMac",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "DispatchMac", targets: ["DispatchMac"])
    ],
    targets: [
        .executableTarget(name: "DispatchMac"),
        .testTarget(name: "DispatchMacTests", dependencies: ["DispatchMac"])
    ]
)
