import SwiftUI

struct AgentsView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var editingAgent: AgentTerminal?
    @State private var nickname = ""
    private let columns = [GridItem(.adaptive(minimum: 280), spacing: 12)]

    /// 카드는 세 블록으로 읽힌다. 누구인가(아이덴티티) → 어디서 무엇을
    /// 맡았나(할당) → 어디서 일하나(컨텍스트). 액션은 맨 아래다.
    private func agentCard(number: Int, agent: AgentTerminal) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            identityBlock(number: number, agent: agent)
            Divider().padding(.vertical, 11)
            assignmentBlock(agent)
            Divider().padding(.vertical, 11)
            contextBlock(agent)
            Spacer(minLength: 11)
            actionBlock(agent)
        }
        .padding(16)
        .background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
    }

    private func identityBlock(number: Int, agent: AgentTerminal) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top, spacing: 9) {
                // 번호는 상태색을 함께 진다. 상태 표시를 따로 두지 않는다.
                Text("\(number)")
                    .font(.caption.bold().monospaced())
                    .foregroundStyle(.white)
                    .frame(width: 21, height: 21)
                    .background(statusColor(agent.lifecycle), in: Circle())
                VStack(alignment: .leading, spacing: 2) {
                    // 연결해도 터미널창 이름을 유지한다. localName은 연결하면서
                    // 붙는 진단용 식별자라 아래로 내린다.
                    Text(agent.nickname?.isEmpty == false ? agent.nickname! : agent.title)
                        .font(.headline).lineLimit(1)
                    if let secondary = secondaryIdentity(agent) {
                        Text(secondary)
                            .font(.caption2).foregroundStyle(.tertiary).lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 5) {
                Text(agent.provider.uppercased())
                    .font(.caption2.bold()).foregroundStyle(.green)
                Text("·").font(.caption2).foregroundStyle(.tertiary)
                Text(agent.lifecycle).font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    /// 별명을 붙였으면 원래 창 이름을, 아니면 진단용 식별자를 보여준다.
    private func secondaryIdentity(_ agent: AgentTerminal) -> String? {
        if agent.nickname?.isEmpty == false { return agent.title }
        return agent.localName
    }

    private func assignmentBlock(_ agent: AgentTerminal) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("ASSIGNMENT")
                .font(.caption2.bold()).foregroundStyle(.tertiary).kerning(0.6)
            if agent.memberships.isEmpty {
                Text(agent.connected ? "역할 없음" : "연결되지 않음")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                ForEach(agent.memberships) { membership in
                    let current = membership.projectID == model.selectedProjectID
                    HStack(spacing: 5) {
                        Text(membership.projectName)
                            .font(.caption2).foregroundStyle(.secondary)
                        Image(systemName: "chevron.right")
                            .font(.system(size: 7)).foregroundStyle(.tertiary)
                        Text(membership.roleName).font(.caption2.bold())
                    }
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(
                        current ? Color.blue.opacity(0.14) : Color.secondary.opacity(0.1),
                        in: Capsule()
                    )
                    .foregroundStyle(current ? .blue : .secondary)
                }
            }
        }
    }

    private func contextBlock(_ agent: AgentTerminal) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(agent.cwd ?? "-")
                .font(.caption).foregroundStyle(.secondary)
                .lineLimit(2).frame(height: 32, alignment: .topLeading)
            if let git = agent.git {
                HStack(spacing: 6) {
                    Image(systemName: "point.topleft.down.to.point.bottomright.curvepath")
                    Text(git.branch ?? "detached HEAD").lineLimit(1)
                    if let head = git.head {
                        Text(head).monospaced().foregroundStyle(.tertiary)
                    }
                    if git.dirty {
                        Text("DIRTY").font(.caption2.bold()).foregroundStyle(.orange)
                    }
                    Spacer(minLength: 0)
                    Text("VERIFIED").font(.caption2.bold()).foregroundStyle(.green)
                }.font(.caption).help(git.worktree)
            }
        }
    }

    private func actionBlock(_ agent: AgentTerminal) -> some View {
        HStack {
            Button("Open terminal") {
                Task { await model.agentAction("focus", surfaceID: agent.surfaceID) }
            }
            if agent.connected, agent.localName != nil {
                Button("Rename") { nickname = agent.nickname ?? ""; editingAgent = agent }
            }
            Spacer()
            Button(agent.connected ? "Disconnect" : "Connect") {
                Task { await model.agentAction("toggle", surfaceID: agent.surfaceID) }
            }
            .tint(agent.connected ? .red : .accentColor)
            .disabled(!agent.connected && !agent.bindingVerified)
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading) {
                        Text("Agents").font(.title.bold())
                        Text("열려 있는 cmux 에이전트를 재시작 없이 연결합니다.")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
                }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(Array(model.snapshot.agents.enumerated()), id: \.element.id) {
                        index, agent in
                        agentCard(number: index + 1, agent: agent)
                    }
                }
            }.padding(24)
        }
        .sheet(item: $editingAgent) { agent in
            VStack(alignment: .leading, spacing: 16) {
                Text("Agent nickname").font(.title2.bold())
                Text(agent.localName ?? agent.title).foregroundStyle(.secondary)
                TextField("Nickname", text: $nickname)
                Text("비워두면 자동 이름을 사용합니다.").font(.caption).foregroundStyle(.secondary)
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
}
