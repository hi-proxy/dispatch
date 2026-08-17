// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "FungisMac",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "FungisMac", targets: ["FungisMac"])
    ],
    targets: [
        .executableTarget(name: "FungisMac"),
        .testTarget(name: "FungisMacTests", dependencies: ["FungisMac"])
    ]
)
