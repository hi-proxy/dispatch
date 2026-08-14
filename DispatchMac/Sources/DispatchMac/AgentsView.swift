import SwiftUI

struct AgentsView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var editingAgent: AgentTerminal?
    @State private var nickname = ""
    private let columns = [GridItem(.adaptive(minimum: 280), spacing: 12)]

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
                    ForEach(model.snapshot.agents) { agent in
                        VStack(alignment: .leading, spacing: 11) {
                            HStack {
                                Text(agent.provider.uppercased()).font(.caption.bold()).foregroundStyle(.green)
                                Spacer(); Circle().fill(statusColor(agent.lifecycle)).frame(width: 8, height: 8)
                                Text(agent.lifecycle).font(.caption).foregroundStyle(.secondary)
                            }
                            Text(agent.nickname?.isEmpty == false ? agent.nickname! : (agent.localName ?? agent.title)).font(.headline)
                            if let nickname = agent.nickname, !nickname.isEmpty {
                                Text(agent.localName ?? agent.title).font(.caption2).foregroundStyle(.tertiary)
                            }
                            if !agent.memberships.isEmpty {
                                VStack(alignment: .leading, spacing: 6) {
                                    ForEach(agent.memberships) { membership in
                                        Text("\(membership.projectName) / \(membership.roleName)")
                                            .font(.caption2.bold()).padding(.horizontal, 8).padding(.vertical, 4)
                                            .background(
                                                membership.projectID == model.selectedProjectID
                                                    ? Color.blue.opacity(0.14) : Color.secondary.opacity(0.1),
                                                in: Capsule()
                                            )
                                            .foregroundStyle(
                                                membership.projectID == model.selectedProjectID ? .blue : .secondary
                                            )
                                    }
                                }
                            } else if agent.connected {
                                Label("No project role assigned", systemImage: "person.badge.key")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Text(agent.cwd ?? "-").font(.caption).foregroundStyle(.secondary)
                                .lineLimit(2).frame(height: 34, alignment: .topLeading)
                            if let git = agent.git {
                                HStack(spacing: 6) {
                                    Image(systemName: "point.topleft.down.to.point.bottomright.curvepath")
                                    Text(git.branch ?? "detached HEAD").lineLimit(1)
                                    if let head = git.head { Text(head).monospaced().foregroundStyle(.tertiary) }
                                    if git.dirty { Text("DIRTY").font(.caption2.bold()).foregroundStyle(.orange) }
                                    Spacer()
                                    Text("VERIFIED").font(.caption2.bold()).foregroundStyle(.green)
                                }.font(.caption).help(git.worktree)
                            }
                            HStack {
                                Button("Open terminal") { Task { await model.agentAction("focus", surfaceID: agent.surfaceID) } }
                                if agent.connected, agent.localName != nil {
                                    Button("Rename") { nickname = agent.nickname ?? ""; editingAgent = agent }
                                }
                                Spacer()
                                Button(agent.connected ? "Disconnect" : "Connect") {
                                    Task { await model.agentAction("toggle", surfaceID: agent.surfaceID) }
                                }.tint(agent.connected ? .red : .accentColor)
                                    .disabled(!agent.connected && !agent.bindingVerified)
                            }
                        }.padding(16).background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
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
