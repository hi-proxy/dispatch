import AppKit
@preconcurrency import UserNotifications

@MainActor
final class NotificationCoordinator: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationCoordinator()
    private var initialized = false
    private var latestSequence = 0
    /// 이미 알린 조작 대기 세션. 상태가 풀리면 지워 다음에 다시 알린다.
    private var announcedAwaiting: Set<String> = []

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
        notifyAwaitingInput(snapshot)
        guard previous > 0 else { return }
        for message in snapshot.timeline where message.seq > previous {
            notify(message)
        }
    }

    /// 에이전트가 권한 확인이나 선택 화면에서 멈추면 한 번 알린다. 터미널을
    /// 띄워 두지 않으면 막힌 걸 모르고 지나가기 때문이다.
    private func notifyAwaitingInput(_ snapshot: DispatchSnapshot) {
        let waiting = snapshot.agents.filter(\.awaitingInput)
        let waitingIDs = Set(waiting.map(\.surfaceID))
        announcedAwaiting.formIntersection(waitingIDs)
        for agent in waiting where !announcedAwaiting.contains(agent.surfaceID) {
            announcedAwaiting.insert(agent.surfaceID)
            let content = UNMutableNotificationContent()
            content.title = "터미널 확인이 필요합니다"
            content.subtitle = agent.nickname?.isEmpty == false ? agent.nickname! : agent.title
            // 화면이 빈 프롬프트가 아니라는 것만 안다. 무엇을 묻는지까지는
            // 읽지 않으므로 단정하지 않는다.
            content.body = "빈 프롬프트가 아닙니다. 권한 확인이나 선택 화면일 수 있습니다."
            content.sound = .default
            UNUserNotificationCenter.current().add(
                UNNotificationRequest(
                    identifier: "dispatch-awaiting-\(agent.surfaceID)",
                    content: content, trigger: nil
                )
            )
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
