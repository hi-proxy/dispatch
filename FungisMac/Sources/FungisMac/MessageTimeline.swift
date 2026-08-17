import Foundation

enum MessageTimeline {
    static func merging(
        _ existing: [ChatMessage], _ incoming: [ChatMessage]
    ) -> [ChatMessage] {
        var bySequence = Dictionary(uniqueKeysWithValues: existing.map { ($0.seq, $0) })
        for message in incoming { bySequence[message.seq] = message }
        return bySequence.values.sorted { $0.seq < $1.seq }
    }
}

enum TimelinePinTracker {
    static func activePinID(
        positions: [String: CGFloat], viewportHeight: CGFloat
    ) -> String? {
        positions
            .filter { $0.value >= 0 && $0.value <= viewportHeight }
            .min { lhs, rhs in
                abs(lhs.value - viewportHeight / 2)
                    < abs(rhs.value - viewportHeight / 2)
            }?.key
    }
}
