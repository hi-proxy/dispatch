import Foundation
import Testing
@testable import DispatchMac

@Test func timelineMergeSortsDeduplicatesAndUsesFreshMetadata() throws {
    let old = try message(seq: 8, body: "old")
    let earliest = try message(seq: 3, body: "earliest")
    let refreshed = try message(seq: 8, body: "refreshed")
    let newest = try message(seq: 12, body: "newest")

    let merged = MessageTimeline.merging([old], [newest, earliest, refreshed])

    #expect(merged.map(\.seq) == [3, 8, 12])
    #expect(merged[1].body == "refreshed")
}

@Test func timelinePinOnlyLightsWhileItsDividerIsVisible() {
    #expect(TimelinePinTracker.activePinID(
        positions: ["old": -300, "next": 900], viewportHeight: 700
    ) == nil)
    #expect(TimelinePinTracker.activePinID(
        positions: ["top": 40, "middle": 330, "below": 760], viewportHeight: 700
    ) == "middle")
}

private func message(seq: Int, body: String) throws -> ChatMessage {
    let json: [String: Any] = [
        "seq": seq,
        "sender_id": "agent",
        "sender_name": "Agent",
        "body": body,
        "created_at": "2026-08-14T00:00:00.000Z",
        "recipients": [],
        "references": [],
        "tags": [],
        "detected_contexts": [],
        "role_recipients": [],
    ]
    return try JSONDecoder().decode(
        ChatMessage.self, from: JSONSerialization.data(withJSONObject: json)
    )
}
