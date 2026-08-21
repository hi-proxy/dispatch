import Testing
import Foundation
@testable import FungisMac

/// 앱을 열었을 때 어느 방에 서 있나. 지워진 방을 가리킨 채 뜨던 것을 여기서
/// 붙잡는다 — 헤더에는 이름이 보이는데 좌측 목록에서는 아무것도 안 골라져
/// 있어서, 화면만 보면 정상처럼 보였다.
private let roomKey = "selectedProjectID"

@MainActor
private func room(_ id: String, kind: String? = nil) -> FungisProject {
    FungisProject(
        id: id, name: id, createdAt: "2026-08-20T00:00:00Z",
        lastMessageSeq: nil, kind: kind
    )
}

@MainActor
private func snapshotWith(project: String, rooms: [FungisProject]) -> FungisSnapshot {
    var value = FungisSnapshot.empty
    value.projectID = project
    value.projects = rooms
    return value
}

@MainActor
private func chatMessage(seq: Int, body: String) throws -> ChatMessage {
    let json: [String: Any] = [
        "seq": seq, "project_seq": seq,
        "sender_id": "pm", "sender_name": "PM", "body": body,
        "created_at": "2026-08-21T00:00:00.000Z",
        "recipients": [], "references": [], "tags": [],
        "detected_contexts": [], "role_recipients": [],
    ]
    return try JSONDecoder().decode(
        ChatMessage.self, from: JSONSerialization.data(withJSONObject: json)
    )
}

@MainActor
private func role(project: String, name: String) -> WorkspaceRole {
    WorkspaceRole(
        id: "\(project)-\(name)", workspaceID: project, name: name,
        onboardingPrompt: "", assigned: false, assignmentID: nil,
        agentID: nil, agentName: nil, assignedAt: nil, onboardingSent: false,
        sessionConnected: false, hasAvatar: false, avatarUpdatedAt: nil
    )
}

@Test @MainActor func firstLaunchStartsInHQ() {
    // 기억한 것이 없으면 HQ 다. 아무 방이나 고르면 남의 방에 떨어져 거기 대고
    // 말하게 된다.
    UserDefaults.standard.removeObject(forKey: roomKey)
    #expect(AppModel().selectedProjectID == AppModel.homeRoom)
}

@Test @MainActor func theRoomYouLeftIsTheRoomYouReturnTo() {
    UserDefaults.standard.removeObject(forKey: roomKey)
    let model = AppModel()
    model.selectProject("fungis")
    // 다음에 열면 거기서 시작한다.
    #expect(AppModel().selectedProjectID == "fungis")
    UserDefaults.standard.removeObject(forKey: roomKey)
    _ = model
}

@Test @MainActor func aRoomThatIsGoneFallsBackToHQ() {
    UserDefaults.standard.removeObject(forKey: roomKey)
    let model = AppModel()
    model.selectProject("deleted-room")
    #expect(model.selectedProjectID == "deleted-room")

    // 서버 목록에 그 방이 없다. 헤더만 이름을 들고 있는 상태였다.
    model.applyForTesting(snapshotWith(
        project: "deleted-room",
        rooms: [room("hq", kind: "hq"), room("fungis")]
    ))
    #expect(model.selectedProjectID == AppModel.homeRoom)
    UserDefaults.standard.removeObject(forKey: roomKey)
}

@Test @MainActor func aLiveRoomIsLeftAlone() {
    // 폴백이 너무 세면 멀쩡한 방에서도 튕겨 나간다.
    UserDefaults.standard.removeObject(forKey: roomKey)
    let model = AppModel()
    model.selectProject("fungis")
    model.applyForTesting(snapshotWith(
        project: "fungis",
        rooms: [room("hq", kind: "hq"), room("fungis")]
    ))
    #expect(model.selectedProjectID == "fungis")
    UserDefaults.standard.removeObject(forKey: roomKey)
}

@Test @MainActor func switchingRoomsNeverStagesOneRoomUnderAnotherRoomsName() throws {
    UserDefaults.standard.removeObject(forKey: roomKey)
    let model = AppModel()
    model.selectProject("test-pj-3")
    var testRoom = snapshotWith(
        project: "test-pj-3",
        rooms: [room("test-pj-3"), room("fungis")]
    )
    testRoom.timeline = [try chatMessage(seq: 1, body: "test only")]
    testRoom.roles = [role(project: "test-pj-3", name: "tester")]
    model.applyForTesting(testRoom)

    model.selectProject("fungis")

    #expect(model.snapshot.projectID == "fungis")
    #expect(model.snapshot.timeline.isEmpty)
    #expect(model.snapshot.roles.isEmpty)

    var fungis = snapshotWith(
        project: "fungis",
        rooms: [room("test-pj-3"), room("fungis")]
    )
    fungis.timeline = [try chatMessage(seq: 2, body: "fungis only")]
    fungis.roles = [role(project: "fungis", name: "exec")]
    model.applyForTesting(fungis)
    #expect(model.snapshot.timeline.map(\.body) == ["fungis only"])

    model.selectProject("test-pj-3")
    #expect(model.snapshot.projectID == "test-pj-3")
    #expect(model.snapshot.timeline.map(\.body) == ["test only"])
    #expect(model.snapshot.roles.isEmpty)
    UserDefaults.standard.removeObject(forKey: roomKey)
}
