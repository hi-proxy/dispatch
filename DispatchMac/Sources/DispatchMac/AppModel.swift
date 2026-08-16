import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @Published var snapshot = DispatchSnapshot.empty
    @Published var selectedTargets: Set<String> = []
    @Published var selectedRoles: Set<String> = []
    @Published var isConnected = false
    @Published var errorMessage: String?
    @Published var isMutating = false
    @Published var selectedProjectID = "local"
    @Published private(set) var isLoadingHistory = false
    @Published private(set) var hasOlderMessages = true
    /// 첫 snapshot이 아직 도착하지 않은 구간. 빈 타임라인을 "메시지 없음"으로
    /// 오해시키지 않으려고 구분한다.
    @Published private(set) var isLoadingTimeline = true

    private let api = DispatchAPI()
    private var timelineProjectID: String?
    private var prefetchedProjectID: String?
    private var streamTask: Task<Void, Error>?
    private var switchingProject = false
    /// 방을 나가도 읽어둔 메시지를 버리지 않는다. 다시 들어올 때 네트워크를
    /// 기다리지 않고 곧바로 같은 자리를 보여주기 위한 것이다.
    private var timelineCache: [String: (messages: [ChatMessage], hasOlder: Bool)] = [:]

    init() {
        NotificationCoordinator.shared.start()
    }

    func run() async {
        while !Task.isCancelled {
            let streamingProject = selectedProjectID
            do {
                try await DaemonManager.shared.ensureRunning()
                // WebSocket 첫 push를 기다리지 않고 HTTP로 화면을 먼저 채운다.
                await refresh()
                let task = Task {
                    for try await fresh in api.snapshots(projectID: streamingProject) {
                        try Task.checkCancellation()
                        apply(fresh)
                    }
                }
                streamTask = task
                try await task.value
            } catch {
                if !switchingProject {
                    isConnected = false
                    errorMessage = error.localizedDescription
                }
            }
            // 프로젝트를 바꿔 끊은 스트림이면 물러서지 않고 바로 다시 붙는다.
            // 취소는 예외로 끝날 수도, for-await가 조용히 끝날 수도 있다.
            if switchingProject {
                switchingProject = false
                continue
            }
            if !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func refresh() async {
        guard !isMutating else { return }
        do {
            let fresh = try await api.state(projectID: selectedProjectID)
            apply(fresh)
        } catch {
            isConnected = false
            errorMessage = error.localizedDescription
        }
    }

    func send(
        _ body: String, to recipients: [String], roles: [String] = [],
        inReplyTo: Int? = nil,
        track: String? = nil, tags: [String]? = nil,
        inheritContext: Bool = true
    ) async -> Bool {
        await mutate {
            try await api.send(
                projectID: selectedProjectID,
                recipientIDs: recipients, roleIDs: roles, body: body,
                inReplyTo: inReplyTo,
                track: track, tags: tags, inheritContext: inheritContext
            )
        }
    }

    func createRole(name: String, onboardingPrompt: String) async -> Bool {
        await mutate { try await api.createRole(projectID: selectedProjectID, name: name, onboardingPrompt: onboardingPrompt) }
    }

    func updateRole(id: String, name: String, onboardingPrompt: String) async -> Bool {
        await mutate { try await api.updateRole(id: id, name: name, onboardingPrompt: onboardingPrompt) }
    }

    func deleteRole(id: String) async {
        _ = await mutate { try await api.deleteRole(id: id) }
    }

    func assignRole(id: String, agentID: String, sendOnboarding: Bool) async -> Bool {
        await mutate { try await api.assignRole(id: id, agentID: agentID, sendOnboarding: sendOnboarding) }
    }

    func unassignRole(id: String) async {
        _ = await mutate { try await api.unassignRole(id: id) }
    }

    func roleHistory(id: String) async -> [RoleAssignment] {
        do { return try await api.roleHistory(id: id) }
        catch { errorMessage = error.localizedDescription; return [] }
    }

    func putRoleAvatar(id: String, data: Data, mediaType: String) async -> Bool {
        await mutate { try await api.putRoleAvatar(id: id, data: data, mediaType: mediaType) }
    }

    func deleteRoleAvatar(id: String) async -> Bool {
        await mutate { try await api.deleteRoleAvatar(id: id) }
    }

    func agentAction(_ action: String, surfaceID: String) async {
        _ = await mutate { try await api.act(on: surfaceID, action: action) }
    }

    func setNickname(localName: String, nickname: String) async -> Bool {
        await mutate { try await api.setNickname(localName: localName, nickname: nickname) }
    }

    func saveShared(key: String, value: String) async -> Bool {
        await mutate { try await api.putShared(projectID: selectedProjectID, key: key, value: value) }
    }

    func deleteShared(key: String) async {
        _ = await mutate { try await api.deleteShared(projectID: selectedProjectID, key: key) }
    }

    /// 이 프로젝트의 담당자가 배정된 역할 전부에 짧은 `dispatch init` 호출문을
    /// 보낸다. 사용법 본문은 에이전트가 bootstrap API에서 읽는다.
    ///
    /// 채팅 입력창의 수신자 선택과 엮지 않는다. 그쪽은 대화 맥락이라 수시로
    /// 바뀌는데 이건 셋업 행위다. 엮어 두면 대화하려고 고른 상대에게 셋업
    /// 메시지가 나간다.
    func initializeChat() async {
        let roles = snapshot.roles.filter(\.assigned).map(\.id)
        guard !roles.isEmpty else { return }
        _ = await send(
            "[dispatch:init] 사용법과 현재 역할 구성을 불러오세요: "
                + "dispatch init --project \(selectedProjectID)",
            to: [],
            roles: roles,
            tags: ["dispatch-init"],
            inheritContext: false
        )
    }

    func selectProject(_ id: String) {
        guard id != selectedProjectID else { return }
        timelineCache[selectedProjectID] = (Array(snapshot.timeline.suffix(10)), hasOlderMessages)
        selectedProjectID = id
        if let cached = timelineCache[id] {
            // 들어갈 때는 최신 10건만 붙인다. 쌓아둔 과거까지 한꺼번에 붙이면
            // 보이지도 않는 행을 전부 다시 레이아웃하게 된다.
            snapshot.timeline = Array(cached.messages.suffix(10))
            hasOlderMessages = cached.hasOlder || cached.messages.count > 10
            // 캐시를 살려 두고 refresh 결과를 병합한다.
            timelineProjectID = id
            prefetchedProjectID = nil
            isLoadingTimeline = false
        } else {
            snapshot.timeline = []
            hasOlderMessages = true
            timelineProjectID = nil
            prefetchedProjectID = nil
            isLoadingTimeline = true
        }
        selectedTargets.removeAll()
        selectedRoles.removeAll()
        // 옛 프로젝트 스트림은 서버가 다음 snapshot을 보낼 때까지 스스로 끝나지
        // 않는다. 끊어야 run 루프가 새 프로젝트로 곧바로 다시 붙는다.
        switchingProject = true
        streamTask?.cancel()
    }

    func createProject(name: String) async -> Bool {
        do {
            let project = try await api.createProject(name: name)
            // 직접 대입하면 수신자 선택과 스트림이 이전 방에 남는다.
            // 방 전환 경로를 그대로 탄다.
            selectProject(project.id)
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func updateProject(id: String, name: String) async -> Bool {
        await mutate { _ = try await api.updateProject(id: id, name: name) }
    }

    func setProjectRepository(projectID: String, path: String) async -> Bool {
        await mutate { try await api.setProjectRepository(projectID: projectID, path: path) }
    }

    func deleteProjectRepository(projectID: String) async -> Bool {
        await mutate { try await api.deleteProjectRepository(projectID: projectID) }
    }

    func updatePMProfile(displayName: String) async -> Bool {
        await mutate { try await api.updatePMProfile(displayName: displayName) }
    }

    func putPMAvatar(data: Data, mediaType: String) async -> Bool {
        await mutate { try await api.putPMAvatar(data: data, mediaType: mediaType) }
    }

    func deletePMAvatar() async -> Bool {
        await mutate { try await api.deletePMAvatar() }
    }

    func createBookmark(messageSeq: Int, label: String) async -> Bool {
        await mutate {
            try await api.createBookmark(
                projectID: selectedProjectID, messageSeq: messageSeq, label: label
            )
        }
    }

    func deleteBookmark(id: String) async {
        _ = await mutate {
            try await api.deleteBookmark(projectID: selectedProjectID, bookmarkID: id)
        }
    }

    func createTimelinePin(afterMessageSeq: Int, label: String) async -> Bool {
        await mutate {
            try await api.createTimelinePin(
                projectID: selectedProjectID,
                afterMessageSeq: afterMessageSeq,
                label: label
            )
        }
    }

    func deleteTimelinePin(id: String) async {
        _ = await mutate {
            try await api.deleteTimelinePin(projectID: selectedProjectID, pinID: id)
        }
    }

    func loadOlderMessages() async {
        guard !isLoadingHistory, hasOlderMessages,
              timelineProjectID == selectedProjectID,
              let earliestSequence = snapshot.timeline.first?.seq else { return }
        let projectID = selectedProjectID
        isLoadingHistory = true
        defer { isLoadingHistory = false }
        do {
            let page = try await api.history(
                projectID: projectID, before: earliestSequence, limit: 50
            )
            guard projectID == selectedProjectID,
                  timelineProjectID == projectID else { return }
            var updated = snapshot
            updated.timeline = MessageTimeline.merging(updated.timeline, page)
            snapshot = updated
            if page.count < 50 { hasOlderMessages = false }
            timelineCache[projectID] = (Array(updated.timeline.suffix(10)), hasOlderMessages)
        } catch {
            guard projectID == selectedProjectID else { return }
            errorMessage = error.localizedDescription
        }
    }

    func ensureMessageLoaded(_ sequence: Int) async {
        while !snapshot.timeline.contains(where: { $0.seq == sequence }),
              hasOlderMessages, timelineProjectID == selectedProjectID {
            if isLoadingHistory {
                try? await Task.sleep(for: .milliseconds(50))
                continue
            }
            let previousEarliest = snapshot.timeline.first?.seq
            await loadOlderMessages()
            if snapshot.timeline.first?.seq == previousEarliest { break }
        }
    }

    private func mutate(_ operation: () async throws -> Void) async -> Bool {
        isMutating = true
        defer { isMutating = false }
        do {
            try await operation()
            let fresh = try await api.state(projectID: selectedProjectID)
            apply(fresh)
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    private func apply(_ freshSnapshot: DispatchSnapshot) {
        var fresh = freshSnapshot
        guard fresh.projectID == selectedProjectID else { return }
        let isNewTimeline = timelineProjectID != fresh.projectID
        if isNewTimeline {
            timelineProjectID = fresh.projectID
            hasOlderMessages = fresh.timeline.count == 10
        } else {
            fresh.timeline = MessageTimeline.merging(snapshot.timeline, fresh.timeline)
        }
        snapshot = fresh
        isLoadingTimeline = false
        timelineCache[fresh.projectID] = (Array(fresh.timeline.suffix(10)), hasOlderMessages)
        NotificationCoordinator.shared.consume(freshSnapshot)
        let available = Set(fresh.targets.map(\.id))
        selectedTargets.formIntersection(available)
        let availableRoles = Set(fresh.roles.map(\.id))
        selectedRoles.formIntersection(availableRoles)
        // 역할은 이 프로젝트 소속이라 자동으로 골라도 안전하다. 세션 목록은
        // 전역이므로 자동으로 고르면 다른 방 담당에게 발송될 수 있다.
        if selectedTargets.isEmpty, selectedRoles.isEmpty,
           let firstRole = fresh.roles.first?.id {
            selectedRoles.insert(firstRole)
        }
        isConnected = true
        errorMessage = nil
        // 타임라인이 역순으로 쌓이므로 과거는 레이아웃 뒤쪽에 붙는다. 이미
        // 배치된 행을 다시 재지 않아 진입 직후 병합이 다시 가능해졌다.
        // 타임라인이 역순으로 쌓이므로 과거는 레이아웃 뒤쪽에 붙는다. 이미
        // 배치된 행을 다시 재지 않아 진입 직후 병합이 다시 가능해졌다.
        if hasOlderMessages, prefetchedProjectID != fresh.projectID {
            prefetchedProjectID = fresh.projectID
            Task { await loadOlderMessages() }
        }
    }
}
