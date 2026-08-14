import Foundation

struct MentionCandidate: Equatable {
    enum Kind: Equatable { case role, target }

    let token: String
    let id: String
    let kind: Kind
}

struct MentionRoute: Equatable {
    let body: String
    let roleIDs: [String]
    let targetIDs: [String]
}

enum MentionRoutingError: Error, Equatable {
    case unknown(String)
    case ambiguous(String)
    case emptyBody

    var message: String {
        switch self {
        case .unknown(let token): "알 수 없는 수신자: @\(token)"
        case .ambiguous(let token): "수신자 호칭이 중복됨: @\(token)"
        case .emptyBody: "수신자 뒤에 보낼 내용을 입력하세요."
        }
    }
}

enum MentionRouting {
    static func parse(
        _ draft: String, candidates: [MentionCandidate]
    ) -> Result<MentionRoute, MentionRoutingError>? {
        var cursor = draft.startIndex
        skipWhitespace(in: draft, cursor: &cursor)
        guard cursor < draft.endIndex, draft[cursor] == "@" else { return nil }

        var tokens: [String] = []
        while cursor < draft.endIndex, draft[cursor] == "@" {
            cursor = draft.index(after: cursor)
            let tokenStart = cursor
            while cursor < draft.endIndex, !draft[cursor].isWhitespace {
                cursor = draft.index(after: cursor)
            }
            let token = String(draft[tokenStart..<cursor])
            guard !token.isEmpty else { return .failure(.unknown("")) }
            tokens.append(token)
            skipWhitespace(in: draft, cursor: &cursor)
        }

        let body = String(draft[cursor...])
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return .failure(.emptyBody) }

        var roleIDs: [String] = []
        var targetIDs: [String] = []
        for token in tokens {
            let roleMatches = matches(token, in: candidates.filter { $0.kind == .role })
            let resolved: MentionCandidate
            if roleMatches.count == 1 {
                resolved = roleMatches[0]
            } else if roleMatches.count > 1 {
                return .failure(.ambiguous(token))
            } else {
                let targetMatches = matches(
                    token, in: candidates.filter { $0.kind == .target }
                )
                guard targetMatches.count == 1 else {
                    return .failure(
                        targetMatches.isEmpty ? .unknown(token) : .ambiguous(token)
                    )
                }
                resolved = targetMatches[0]
            }

            switch resolved.kind {
            case .role:
                if !roleIDs.contains(resolved.id) { roleIDs.append(resolved.id) }
            case .target:
                if !targetIDs.contains(resolved.id) { targetIDs.append(resolved.id) }
            }
        }
        return .success(MentionRoute(
            body: body, roleIDs: roleIDs, targetIDs: targetIDs
        ))
    }

    private static func matches(
        _ token: String, in candidates: [MentionCandidate]
    ) -> [MentionCandidate] {
        candidates.filter {
            $0.token.compare(token, options: [.caseInsensitive, .diacriticInsensitive])
                == .orderedSame
        }
    }

    private static func skipWhitespace(in value: String, cursor: inout String.Index) {
        while cursor < value.endIndex, value[cursor].isWhitespace {
            cursor = value.index(after: cursor)
        }
    }
}
