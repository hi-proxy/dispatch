import Testing
import Foundation
@testable import FungisMac

/// 방마다 수신자 선택이 유지되는지. 세 번 고쳤는데 세 번 다 화면으로만 확인을
/// 미뤘던 자리라, 논리 자체를 여기서 붙잡아 둔다.
@MainActor
private func makeModel() -> AppModel {
    UserDefaults.standard.removeObject(forKey: "recipientMemory")
    return AppModel()
}

@MainActor
private func snapshot(project: String, roles: [String]) -> FungisSnapshot {
    var value = FungisSnapshot.empty
    value.projectID = project
    value.roles = roles.map {
        WorkspaceRole(
            id: $0, workspaceID: project, name: $0, onboardingPrompt: "",
            assigned: true, assignmentID: nil, agentID: "agent-\($0)",
            agentName: nil, assignedAt: nil, onboardingSent: false,
            sessionConnected: true, hasAvatar: false, avatarUpdatedAt: nil
        )
    }
    value.projects = [
        FungisProject(id: project, name: project, createdAt: "", lastMessageSeq: nil)
    ]
    return value
}

@Test @MainActor func recipientsSurviveARoundTripBetweenRooms() {
    let model = makeModel()
    model.selectedProjectID = "A"
    model.selectedRoles = ["cto"]
    model.referenceRoles = ["a1"]

    model.selectProject("B")
    #expect(model.selectedRoles == [])
    #expect(model.referenceRoles == [])

    model.selectProject("A")
    #expect(model.selectedRoles == ["cto"])
    #expect(model.referenceRoles == ["a1"])
}

@Test @MainActor func clearedRecipientsStayCleared() {
    // 자동 고르기가 매번 돌아 PM이 지운 선택을 되살리던 것이 진짜 원인이었다.
    let model = makeModel()
    model.selectedProjectID = "A"
    model.applyForTesting(snapshot(project: "A", roles: ["cto", "a1"]))
    model.selectedRoles = []
    model.referenceRoles = ["a1"]

    model.applyForTesting(snapshot(project: "A", roles: ["cto", "a1"]))
    #expect(model.selectedRoles == [])
    #expect(model.referenceRoles == ["a1"])
}

@Test @MainActor func firstVisitPicksARoleSoTheRoomIsUsable() {
    let model = makeModel()
    model.selectedProjectID = "A"
    model.applyForTesting(snapshot(project: "A", roles: ["cto"]))
    #expect(model.selectedRoles == ["cto"])
}

@Test @MainActor func hostedApprovalUsesTheAssignedRoleAsItsIdentity() {
    let model = makeModel()
    model.selectedProjectID = "A"
    model.applyForTesting(snapshot(project: "A", roles: ["tester1", "tester2"]))

    #expect(model.hostedRoleNames(
        projectID: "A", principalID: "agent-tester1"
    ) == ["tester1"])
    #expect(model.hostedRoleNames(
        projectID: "B", principalID: "agent-tester1"
    ).isEmpty)
}
