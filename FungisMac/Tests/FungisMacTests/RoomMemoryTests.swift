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
