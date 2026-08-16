import Foundation

struct DispatchSnapshot: Decodable {
    var projectID: String
    var projects: [DispatchProject]
    var projectRepositories: [ProjectRepository]
    var pmID: String
    var pmProfile: PMProfile
    var targets: [Target]
    var statuses: [AgentStatus]
    var timeline: [ChatMessage]
    var attention: [AttentionRequest]
    var bookmarks: [MessageBookmark]
    var timelinePins: [TimelinePin]
    var shared: [SharedValue]
    var work: [WorkItem]
    var roles: [WorkspaceRole]
    var agents: [AgentTerminal]

    static let empty = DispatchSnapshot(
        projectID: "local", projects: [], projectRepositories: [],
        pmID: "", pmProfile: .empty,
        targets: [], statuses: [], timeline: [], attention: [], bookmarks: [],
        timelinePins: [],
        shared: [], work: [], roles: [], agents: []
    )

    enum CodingKeys: String, CodingKey {
        case projectID = "project_id"
        case projects
        case projectRepositories = "project_repositories"
        case pmID = "pm_id"
        case pmProfile = "pm_profile"
        case targets, statuses, timeline, attention, bookmarks, shared, work, roles, agents
        case timelinePins = "timeline_pins"
    }
}

struct DispatchProject: Decodable, Identifiable, Hashable {
    var id: String
    var name: String
    var createdAt: String
    /// 방에 마지막으로 들어온 메시지 seq. 메시지가 없으면 nil이다.
    var lastMessageSeq: Int?
    enum CodingKeys: String, CodingKey {
        case id, name
        case createdAt = "created_at"
        case lastMessageSeq = "last_message_seq"
    }
}

struct ProjectRepository: Decodable, Identifiable {
    var projectID: String
    var path: String
    var updatedAt: String
    var git: GitContext?
    var id: String { projectID }
    enum CodingKeys: String, CodingKey {
        case projectID = "project_id"
        case path, git
        case updatedAt = "updated_at"
    }
}

struct PMProfile: Decodable {
    var principalID: String
    var displayName: String
    var hasAvatar: Bool
    var avatarUpdatedAt: String?
    static let empty = PMProfile(
        principalID: "", displayName: "PM", hasAvatar: false, avatarUpdatedAt: nil
    )
    enum CodingKeys: String, CodingKey {
        case principalID = "principal_id"
        case displayName = "display_name"
        case hasAvatar = "has_avatar"
        case avatarUpdatedAt = "avatar_updated_at"
    }
}

struct AgentMembership: Decodable, Hashable, Identifiable {
    var agentID: String
    var roleID: String
    var roleName: String
    var projectID: String
    var projectName: String
    var assignedAt: String
    var id: String { "\(projectID):\(roleID)" }
    enum CodingKeys: String, CodingKey {
        case agentID = "agent_id"
        case roleID = "role_id"
        case roleName = "role_name"
        case projectID = "project_id"
        case projectName = "project_name"
        case assignedAt = "assigned_at"
    }
}

struct Target: Decodable, Identifiable, Hashable {
    var localName: String
    var principalID: String
    var nickname: String?
    var provider: String
    var lifecycle: String
    var memberships: [AgentMembership]
    var id: String { localName }
    var displayName: String { nickname?.isEmpty == false ? nickname! : localName }

    enum CodingKeys: String, CodingKey {
        case localName = "local_name"
        case principalID = "principal_id"
        case nickname, provider, lifecycle, memberships
    }
}

struct AgentStatus: Decodable, Identifiable {
    var id: String
    var provider: String
    var lifecycle: String
    var localPending: Int
    var processedSeq: Int

    enum CodingKeys: String, CodingKey {
        case id, provider, lifecycle
        case localPending = "local_pending"
        case processedSeq = "processed_seq"
    }
}

struct MessageRecipient: Decodable {
    var recipientID: String
    var displayName: String
    var receivedAt: String?
    var processedAt: String?

    enum CodingKeys: String, CodingKey {
        case recipientID = "recipient_id"
        case displayName = "display_name"
        case receivedAt = "received_at"
        case processedAt = "processed_at"
    }
}

struct MessageReference: Decodable {
    var principalID: String
    var displayName: String

    enum CodingKeys: String, CodingKey {
        case principalID = "principal_id"
        case displayName = "display_name"
    }
}

struct RoleRecipient: Decodable {
    var roleID: String
    var name: String
    var deliveredAgentID: String?
    var deliveredAt: String?

    enum CodingKeys: String, CodingKey {
        case roleID = "role_id"
        case name
        case deliveredAgentID = "delivered_agent_id"
        case deliveredAt = "delivered_at"
    }
}

struct ChatMessage: Decodable, Identifiable {
    var seq: Int
    var senderID: String
    var senderName: String
    var body: String
    var createdAt: String
    var recipients: [MessageRecipient]
    var references: [MessageReference]
    var pmRelation: String?
    var track: String?
    var tags: [String]
    var inReplyTo: Int?
    var detectedContexts: [DetectedContext]
    var roleRecipients: [RoleRecipient]
    var id: Int { seq }

    enum CodingKeys: String, CodingKey {
        case seq, body, recipients, references, track, tags
        case createdAt = "created_at"
        case detectedContexts = "detected_contexts"
        case roleRecipients = "role_recipients"
        case inReplyTo = "in_reply_to"
        case pmRelation = "pm_relation"
        case senderID = "sender_id"
        case senderName = "sender_name"
    }
}

struct AttentionRequest: Decodable, Identifiable {
    var seq: Int
    var senderID: String
    var senderName: String
    var replyLevel: String
    var body: String
    var pmRelation: String?
    var track: String?
    var tags: [String]
    var detectedContexts: [DetectedContext]
    var id: Int { seq }

    enum CodingKeys: String, CodingKey {
        case seq, body, track, tags
        case detectedContexts = "detected_contexts"
        case pmRelation = "pm_relation"
        case senderID = "sender_id"
        case senderName = "sender_name"
        case replyLevel = "reply_level"
    }
}

struct MessageBookmark: Decodable, Identifiable {
    var id: String
    var messageSeq: Int
    var label: String
    var createdBy: String
    var createdByName: String
    var createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, label
        case messageSeq = "message_seq"
        case createdBy = "created_by"
        case createdByName = "created_by_name"
        case createdAt = "created_at"
    }
}

struct TimelinePin: Decodable, Identifiable {
    var id: String
    var afterMessageSeq: Int
    var label: String
    var createdBy: String
    var createdByName: String
    var createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, label
        case afterMessageSeq = "after_message_seq"
        case createdBy = "created_by"
        case createdByName = "created_by_name"
        case createdAt = "created_at"
    }
}

struct SharedValue: Decodable, Identifiable {
    var key: String
    var value: String
    var version: Int
    var id: String { key }
}

struct WorkItem: Decodable, Identifiable {
    var id: String
    var agentName: String
    var title: String
    var status: String
    var elapsedSeconds: Int
    var lastReport: String?
    var tokenUsage: Int?

    enum CodingKeys: String, CodingKey {
        case id, title, status
        case agentName = "agent_name"
        case elapsedSeconds = "elapsed_seconds"
        case lastReport = "last_report"
        case tokenUsage = "token_usage"
    }
}

struct WorkspaceRole: Decodable, Identifiable {
    var id: String
    var workspaceID: String
    var name: String
    var onboardingPrompt: String
    var assigned: Bool
    var assignmentID: String?
    var agentID: String?
    var agentName: String?
    var assignedAt: String?
    var onboardingSent: Bool
    var sessionConnected: Bool
    var hasAvatar: Bool
    var avatarUpdatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, assigned
        case workspaceID = "workspace_id"
        case onboardingPrompt = "onboarding_prompt"
        case assignmentID = "assignment_id"
        case agentID = "agent_id"
        case agentName = "agent_name"
        case assignedAt = "assigned_at"
        case onboardingSent = "onboarding_sent"
        case sessionConnected = "session_connected"
        case hasAvatar = "has_avatar"
        case avatarUpdatedAt = "avatar_updated_at"
    }
}

struct RoleAssignment: Decodable, Identifiable {
    var id: String
    var roleID: String
    var agentID: String
    var agentName: String
    var assignedAt: String
    var endedAt: String?
    var onboardingSent: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case roleID = "role_id"
        case agentID = "agent_id"
        case agentName = "agent_name"
        case assignedAt = "assigned_at"
        case endedAt = "ended_at"
        case onboardingSent = "onboarding_sent"
    }
}

struct AgentTerminal: Decodable, Identifiable {
    var provider: String
    var agentSessionID: String
    var surfaceID: String
    var title: String
    var cwd: String?
    var lifecycle: String
    var bindingVerified: Bool
    var connected: Bool
    var localName: String?
    var nickname: String?
    var principalID: String?
    var memberships: [AgentMembership]
    var git: GitContext?
    var id: String { "\(provider):\(agentSessionID)" }

    enum CodingKeys: String, CodingKey {
        case provider, title, cwd, lifecycle, connected, nickname, memberships
        case principalID = "principal_id"
        case agentSessionID = "agent_session_id"
        case surfaceID = "surface_id"
        case bindingVerified = "binding_verified"
        case localName = "local_name"
    }
}

struct GitContext: Decodable {
    var repoRoot: String
    var worktree: String
    var commonDir: String?
    var branch: String?
    var branches: [String]
    var head: String?
    var dirty: Bool
    var verified: Bool

    enum CodingKeys: String, CodingKey {
        case repoRoot = "repo_root"
        case worktree
        case commonDir = "common_dir"
        case branch, branches, head, dirty, verified
    }
}

struct DetectedContext: Decodable, Hashable {
    var kind: String
    var value: String
    var verified: Bool
}

enum DeliveryState: String {
    case incoming, sent, received, processed
}

extension ChatMessage {
    func deliveryState(pmID: String) -> DeliveryState {
        guard senderID == pmID else { return .incoming }
        guard !recipients.isEmpty else { return .sent }
        if recipients.allSatisfy({ $0.processedAt != nil }) { return .processed }
        if recipients.allSatisfy({ $0.receivedAt != nil }) { return .received }
        return .sent
    }
}
