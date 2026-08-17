import Testing
@testable import FungisMac

@Test func leadingMentionsRouteToRolesAndPreserveMessageBody() throws {
    let result = MentionRouting.parse(
        "@agent1 @agent2 첫 줄\n둘째 줄",
        candidates: [
            MentionCandidate(token: "agent1", id: "role-1", kind: .role),
            MentionCandidate(token: "agent2", id: "role-2", kind: .role),
        ]
    )
    let route = try result?.get()
    #expect(route?.roleIDs == ["role-1", "role-2"])
    #expect(route?.targetIDs == [])
    #expect(route?.body == "첫 줄\n둘째 줄")
}

@Test func roleMentionTakesPriorityAndUnknownMentionFails() throws {
    let candidates = [
        MentionCandidate(token: "agent1", id: "role-1", kind: .role),
        MentionCandidate(token: "agent1", id: "session-1", kind: .target),
    ]
    let preferred = MentionRouting.parse("@agent1 확인", candidates: candidates)
    let route = try #require(preferred).get()
    #expect(route.roleIDs == ["role-1"])

    let unknown = MentionRouting.parse("@missing 확인", candidates: candidates)
    #expect(unknown == .failure(.unknown("missing")))
}

@Test func ordinaryDraftIsNotAKeyboardSendCommand() {
    #expect(MentionRouting.parse("일반 메시지", candidates: []) == nil)
}
