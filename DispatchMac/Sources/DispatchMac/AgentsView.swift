import SwiftUI

/// 목록에서는 이름만 훑고 세부는 늘 같은 자리에서 읽는다. 카드 격자에서는
/// 경로와 액션이 항목마다 반복돼 눈이 계속 옮겨다녔다.
struct AgentsView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedSurfaceID: String?
    @State private var editingAgent: AgentTerminal?
    @State private var nickname = ""

    var body: some View {
        HStack(spacing: 0) {
            agentList
            Divider()
            detailPane
        }
        .sheet(item: $editingAgent) { agent in
            nicknameEditor(agent)
        }
    }

    private var selectedAgent: AgentTerminal? {
        model.snapshot.agents.first { $0.surfaceID == selectedSurfaceID }
            ?? model.snapshot.agents.first
    }

    // MARK: 목록

    private var agentList: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 3) {
                Text("Agents").font(.title3.bold())
                Text("열려 있는 cmux 에이전트를 재시작 없이 연결합니다.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(.horizontal, 18).padding(.top, 20).padding(.bottom, 14)

            ScrollView {
                LazyVStack(spacing: 1) {
                    ForEach(model.snapshot.agents) { agent in
                        listRow(agent)
                    }
                }.padding(.horizontal, 8).padding(.bottom, 12)
            }
        }
        .frame(width: 274)
        .background(.quaternary.opacity(0.18))
    }

    private func listRow(_ agent: AgentTerminal) -> some View {
        let selected = selectedAgent?.surfaceID == agent.surfaceID
        return Button {
            selectedSurfaceID = agent.surfaceID
        } label: {
            HStack(spacing: 10) {
                statusDot(agent)
                Text(displayName(agent))
                    .font(.callout.weight(selected ? .semibold : .regular))
                    .lineLimit(1)
                Spacer(minLength: 0)
                Text(agent.provider.uppercased())
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 10).padding(.vertical, 8)
            .contentShape(RoundedRectangle(cornerRadius: 8))
            .background(
                selected ? Color.secondary.opacity(0.16) : .clear,
                in: RoundedRectangle(cornerRadius: 8)
            )
        }.buttonStyle(.plain)
    }

    private func statusDot(_ agent: AgentTerminal) -> some View {
        Circle()
            .fill(agent.connected ? statusColor(agent.lifecycle) : .clear)
            .frame(width: 7, height: 7)
            .overlay {
                if !agent.connected {
                    Circle().stroke(Color.secondary.opacity(0.55), lineWidth: 1.5)
                }
            }
    }

    // MARK: 상세

    @ViewBuilder
    private var detailPane: some View {
        if let agent = selectedAgent {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(displayName(agent))
                            .font(.title2.bold()).lineLimit(1)
                        HStack(spacing: 8) {
                            Text(agent.provider.uppercased())
                                .font(.system(size: 10, weight: .semibold))
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 4))
                            Text(statusLabel(agent))
                                .font(.caption).foregroundStyle(statusTint(agent))
                        }
                    }
                    Spacer()
                    Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
                }
                if let secondary = secondaryIdentity(agent) {
                    Text(secondary)
                        .font(.caption).foregroundStyle(.secondary)
                        .padding(.leading, 11).padding(.top, 12)
                        .overlay(alignment: .leading) {
                            Rectangle().fill(.quaternary).frame(width: 2)
                                .padding(.top, 12)
                        }
                }

                Divider().padding(.vertical, 18)

                detailRow("배정") { assignmentValue(agent) }
                detailRow("작업 경로") {
                    Text(agent.cwd ?? "-")
                        .font(.caption.monospaced()).foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                if let git = agent.git {
                    detailRow("GIT") { gitValue(git) }
                }

                Spacer(minLength: 20)
                actionRow(agent)
            }
            .padding(22)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        } else {
            ContentUnavailableView(
                "연결할 에이전트가 없습니다", systemImage: "terminal",
                description: Text("cmux에서 에이전트를 실행하면 여기에 나타납니다.")
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .overlay(alignment: .topTrailing) {
                Button("Done") { dismiss() }.keyboardShortcut(.defaultAction).padding(22)
            }
        }
    }

    private func detailRow<Content: View>(
        _ label: String, @ViewBuilder value: () -> Content
    ) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Text(label)
                .font(.system(size: 10, weight: .semibold)).kerning(0.6)
                .foregroundStyle(.tertiary)
                .frame(width: 62, alignment: .leading)
            value()
            Spacer(minLength: 0)
        }.padding(.bottom, 14)
    }

    @ViewBuilder
    private func assignmentValue(_ agent: AgentTerminal) -> some View {
        if agent.memberships.isEmpty {
            Text(agent.connected ? "역할 없음" : "연결되지 않음")
                .font(.caption).foregroundStyle(.tertiary)
        } else {
            VStack(alignment: .leading, spacing: 5) {
                ForEach(agent.memberships) { membership in
                    let current = membership.projectID == model.selectedProjectID
                    HStack(spacing: 5) {
                        Text(membership.projectName).foregroundStyle(.secondary)
                        Image(systemName: "chevron.right")
                            .font(.system(size: 7)).foregroundStyle(.tertiary)
                        Text(membership.roleName).fontWeight(.medium)
                    }
                    .font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(
                        current ? Color.blue.opacity(0.14) : Color.secondary.opacity(0.1),
                        in: RoundedRectangle(cornerRadius: 6)
                    )
                    .foregroundStyle(current ? .blue : .secondary)
                }
            }
        }
    }

    private func gitValue(_ git: GitContext) -> some View {
        HStack(spacing: 6) {
            Text(git.branch ?? "detached HEAD").lineLimit(1)
            if let head = git.head { Text(head).monospaced().foregroundStyle(.tertiary) }
            if git.dirty {
                Text("DIRTY").font(.caption2.bold()).foregroundStyle(.orange)
            }
            Text("VERIFIED").font(.caption2.bold()).foregroundStyle(.green)
        }.font(.caption).help(git.worktree)
    }

    private func actionRow(_ agent: AgentTerminal) -> some View {
        HStack(spacing: 8) {
            Button(agent.connected ? "Disconnect" : "Connect") {
                Task { await model.agentAction("toggle", surfaceID: agent.surfaceID) }
            }
            .buttonStyle(.borderedProminent)
            .tint(agent.connected ? .red : .accentColor)
            .disabled(!agent.connected && !agent.bindingVerified)
            Button("Open terminal") {
                Task { await model.agentAction("focus", surfaceID: agent.surfaceID) }
            }
            if agent.connected, agent.localName != nil {
                Button("Rename") { nickname = agent.nickname ?? ""; editingAgent = agent }
            }
        }
    }

    // MARK: 표시 규칙

    /// 연결해도 터미널창 이름을 유지한다. localName은 연결하면서 붙는 진단용
    /// 식별자라 부제로 내린다.
    private func displayName(_ agent: AgentTerminal) -> String {
        agent.nickname?.isEmpty == false ? agent.nickname! : agent.title
    }

    private func secondaryIdentity(_ agent: AgentTerminal) -> String? {
        if agent.nickname?.isEmpty == false { return agent.title }
        return agent.localName
    }

    private func statusLabel(_ agent: AgentTerminal) -> String {
        guard agent.connected else {
            return agent.bindingVerified ? "연결되지 않음" : "binding 미검증"
        }
        switch agent.lifecycle {
        case "running": return "작업 중"
        case "needs_input": return "입력 대기 중"
        case "idle": return "대기 중"
        default: return agent.lifecycle
        }
    }

    private func statusTint(_ agent: AgentTerminal) -> Color {
        guard agent.connected else { return .secondary }
        return statusColor(agent.lifecycle)
    }

    private func nicknameEditor(_ agent: AgentTerminal) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Agent nickname").font(.title2.bold())
            Text(agent.title).foregroundStyle(.secondary)
            TextField("Nickname", text: $nickname)
            Text("비워두면 터미널창 이름을 사용합니다.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Cancel") { editingAgent = nil }
                Button("Save") {
                    guard let localName = agent.localName else { return }
                    Task {
                        if await model.setNickname(localName: localName, nickname: nickname) {
                            editingAgent = nil
                        }
                    }
                }.buttonStyle(.borderedProminent)
            }
        }.padding(24).frame(width: 420)
    }
}
