import SwiftUI

@main
struct DispatchMacApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("Dispatch") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 920, minHeight: 620)
                .task { await model.run() }
        }
        .defaultSize(width: 1180, height: 760)
        .commands {
            CommandGroup(after: .sidebar) {
                Button("Refresh") { Task { await model.refresh() } }
                    .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}
