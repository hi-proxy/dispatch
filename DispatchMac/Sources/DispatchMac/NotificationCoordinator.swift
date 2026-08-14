import AppKit
@preconcurrency import UserNotifications

@MainActor
final class NotificationCoordinator: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationCoordinator()
    private var initialized = false
    private var latestSequence = 0

    func start() {
        guard !initialized else { return }
        initialized = true
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        Task { try? await center.requestAuthorization(options: [.alert, .sound, .badge]) }
    }

    func consume(_ snapshot: DispatchSnapshot) {
        let previous = latestSequence
        latestSequence = max(latestSequence, snapshot.timeline.last?.seq ?? 0)
        let actionable = snapshot.attention.filter {
            $0.pmRelation == "confirm" || $0.pmRelation == "direct" || $0.pmRelation == "reference"
        }
        NSApplication.shared.dockTile.badgeLabel = actionable.isEmpty ? nil : "\(actionable.count)"
        guard previous > 0 else { return }
        for message in snapshot.timeline where message.seq > previous {
            notify(message)
        }
    }

    private func notify(_ message: ChatMessage) {
        guard let relation = message.pmRelation,
              relation == "confirm" || relation == "direct" || relation == "reference"
        else { return }
        let content = UNMutableNotificationContent()
        content.title = switch relation {
        case "confirm": "PM confirmation required"
        case "direct": "Message to PM"
        default: "PM referenced"
        }
        content.subtitle = message.senderName
        content.body = message.body
        if relation == "confirm" || relation == "direct" {
            content.sound = .default
        }
        let request = UNNotificationRequest(
            identifier: "dispatch-message-\(message.seq)", content: content, trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }
}
