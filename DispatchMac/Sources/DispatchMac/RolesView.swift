import SwiftUI
import UniformTypeIdentifiers

struct RolesView: View {
    @EnvironmentObject private var model: AppModel
    @State private var showCreate = false
    @State private var editingRole: WorkspaceRole?
    @State private var assigningRole: WorkspaceRole?
    @State private var historyRole: WorkspaceRole?
    @State private var deletingRole: WorkspaceRole?
    @State private var editingPM = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Button("Add role", systemImage: "plus") { showCreate = true }
                    Spacer()
                    Button("Initialize", systemImage: "sparkles") {
                        Task { await model.initializeChat() }
                    }
                    .disabled(
                        model.isMutating
                            || (model.selectedTargets.isEmpty && model.selectedRoles.isEmpty)
                    )
                    .help("Send the Dispatch usage guide to the selected recipients")
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 12)], spacing: 12) {
                    pmCard
                    ForEach(model.snapshot.roles) { role in roleCard(role) }
                }

                if model.snapshot.roles.isEmpty {
                    ContentUnavailableView(
                        "No roles", systemImage: "person.badge.key",
                        description: Text("front1처럼 계속 유지할 역할 주소를 만드세요.")
                    ).frame(maxWidth: .infinity, minHeight: 240)
                }
            }.padding(16)
        }
        .sheet(isPresented: $showCreate) {
            RoleEditor(role: nil) { name, prompt in
                if await model.createRole(name: name, onboardingPrompt: prompt) {
                    showCreate = false
                }
            }
        }
        .sheet(item: $editingRole) { role in
            RoleEditor(role: role) { name, prompt in
                if await model.updateRole(id: role.id, name: name, onboardingPrompt: prompt) {
                    editingRole = nil
                }
            }
        }
        .sheet(item: $assigningRole) { role in
            AssignmentEditor(
                role: role, targets: model.snapshot.targets,
                roles: model.snapshot.roles
            ) { agent, onboarding in
                if await model.assignRole(id: role.id, agentID: agent, sendOnboarding: onboarding) {
                    assigningRole = nil
                }
            }
        }
        .sheet(item: $historyRole) { role in
            AssignmentHistoryView(role: role)
        }
        .sheet(isPresented: $editingPM) { PMProfileEditor() }
        .confirmationDialog(
            "Delete role ‘\(deletingRole?.name ?? "")’? Its message and assignment history remain stored.",
            isPresented: Binding(
                get: { deletingRole != nil },
                set: { if !$0 { deletingRole = nil } }
            ), titleVisibility: .visible
        ) {
            Button("Delete role", role: .destructive) {
                if let role = deletingRole { Task { await model.deleteRole(id: role.id) } }
                deletingRole = nil
            }
        }
    }

    private var pmCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                PMAvatar(profile: model.snapshot.pmProfile, size: 46)
                Text(model.snapshot.pmProfile.displayName).font(.title3.bold())
                Spacer()
                Text("PM · ALWAYS PRESENT").font(.caption2.bold()).foregroundStyle(.purple)
            }
            Text("이 프로젝트의 고정 운영자입니다. 모든 메시지를 보고 직접 개입할 수 있습니다.")
                .font(.caption).foregroundStyle(.secondary)
            Divider()
            HStack { Spacer(); Button("Edit profile") { editingPM = true } }
        }.padding(16)
            .background(Color.purple.opacity(0.07), in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.purple.opacity(0.2)))
    }

    private func roleCard(_ role: WorkspaceRole) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                RoleAvatar(role: role, size: 46)
                Circle().fill(role.assigned && role.sessionConnected ? Color.green : Color.orange).frame(width: 9, height: 9)
                Text(role.name).font(.title3.bold())
                Spacer()
                Text(role.assigned ? (role.sessionConnected ? "ASSIGNED" : "SESSION OFFLINE") : "UNASSIGNED")
                    .font(.caption2.bold()).foregroundStyle(role.assigned && role.sessionConnected ? .green : .orange)
            }
            if role.assigned {
                Label(role.agentName ?? role.agentID ?? "Unknown session", systemImage: "terminal")
                    .font(.callout)
                if let since = role.assignedAt {
                    Text("Assigned since \(since)").font(.caption).foregroundStyle(.secondary)
                }
            } else {
                Text("Messages to this role will wait until a session is assigned.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            HStack(spacing: 8) {
                Label(
                    role.onboardingPrompt.isEmpty ? "No onboarding prompt" : "Onboarding ready",
                    systemImage: role.onboardingPrompt.isEmpty ? "doc" : "doc.text.fill"
                ).font(.caption).foregroundStyle(.secondary)
                Spacer()
            }
            Divider()
            HStack {
                Button(role.assigned ? "Replace" : "Assign") { assigningRole = role }
                    .disabled(model.snapshot.targets.isEmpty)
                if role.assigned {
                    Button("Unassign") { Task { await model.unassignRole(id: role.id) } }
                }
                Spacer()
                Menu {
                    Button("History") { historyRole = role }
                    Button("Edit") { editingRole = role }
                    Button("Delete", role: .destructive) { deletingRole = role }
                } label: {
                    Image(systemName: "ellipsis")
                }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
            }
        }.padding(16)
            .background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct PMProfileEditor: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var importingAvatar = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("PM profile").font(.title2.bold())
            HStack(spacing: 14) {
                PMAvatar(profile: model.snapshot.pmProfile, size: 64)
                Button(model.snapshot.pmProfile.hasAvatar ? "Replace photo" : "Choose photo") {
                    importingAvatar = true
                }
                if model.snapshot.pmProfile.hasAvatar {
                    Button("Remove", role: .destructive) {
                        Task { _ = await model.deletePMAvatar() }
                    }
                }
            }
            TextField("Display name", text: $name)
            HStack { Spacer(); Button("Save") {
                Task { if await model.updatePMProfile(displayName: name) { dismiss() } }
            }.buttonStyle(.borderedProminent).disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) }
        }.padding(24).frame(width: 460)
            .onAppear { name = model.snapshot.pmProfile.displayName }
            .fileImporter(
                isPresented: $importingAvatar,
                allowedContentTypes: [.png, .jpeg, .gif], allowsMultipleSelection: false
            ) { result in
                guard case let .success(urls) = result, let url = urls.first else { return }
                let accessing = url.startAccessingSecurityScopedResource()
                defer { if accessing { url.stopAccessingSecurityScopedResource() } }
                do {
                    let data = try Data(contentsOf: url)
                    let mediaType = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType
                        ?? "application/octet-stream"
                    Task { _ = await model.putPMAvatar(data: data, mediaType: mediaType) }
                } catch { model.errorMessage = error.localizedDescription }
            }
    }
}

private struct RoleEditor: View {
    @EnvironmentObject private var model: AppModel
    let role: WorkspaceRole?
    let save: (String, String) async -> Void
    @State private var name: String
    @State private var prompt: String
    @State private var importingAvatar = false

    init(role: WorkspaceRole?, save: @escaping (String, String) async -> Void) {
        self.role = role
        self.save = save
        _name = State(initialValue: role?.name ?? "")
        _prompt = State(initialValue: role?.onboardingPrompt ?? "")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(role == nil ? "New role" : "Edit role").font(.title2.bold())
            if let role {
                HStack(spacing: 14) {
                    RoleAvatar(role: role, size: 64)
                    VStack(alignment: .leading, spacing: 7) {
                        Button(role.hasAvatar ? "Replace photo" : "Choose photo") {
                            importingAvatar = true
                        }
                        if role.hasAvatar {
                            Button("Remove photo", role: .destructive) {
                                Task { _ = await model.deleteRoleAvatar(id: role.id) }
                            }
                        }
                        Text("PNG, JPEG, or GIF · up to 2 MB")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            } else {
                Text("Save the role first, then add an optional profile photo.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            TextField("Role address, e.g. front1", text: $name)
            Text("One-time onboarding prompt").font(.headline)
            TextEditor(text: $prompt).frame(height: 220).padding(6)
                .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 8))
            Text("The exact text is sent only when you enable onboarding during a new assignment.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Save") { Task { await save(name.trimmingCharacters(in: .whitespacesAndNewlines), prompt) } }
                    .buttonStyle(.borderedProminent)
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }.padding(24).frame(width: 520)
            .fileImporter(
                isPresented: $importingAvatar,
                allowedContentTypes: [.png, .jpeg, .gif], allowsMultipleSelection: false
            ) { result in
                guard let role, case let .success(urls) = result,
                      let url = urls.first else { return }
                let accessing = url.startAccessingSecurityScopedResource()
                defer { if accessing { url.stopAccessingSecurityScopedResource() } }
                do {
                    let data = try Data(contentsOf: url)
                    let mediaType = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType
                        ?? "application/octet-stream"
                    Task { _ = await model.putRoleAvatar(id: role.id, data: data, mediaType: mediaType) }
                } catch {
                    model.errorMessage = error.localizedDescription
                }
            }
    }
}

private struct AssignmentEditor: View {
    let role: WorkspaceRole
    let targets: [Target]
    let roles: [WorkspaceRole]
    let assign: (String, Bool) async -> Void
    @State private var agentID: String
    @State private var sendOnboarding: Bool
    @State private var confirmReassignment = false

    init(
        role: WorkspaceRole, targets: [Target], roles: [WorkspaceRole],
        assign: @escaping (String, Bool) async -> Void
    ) {
        self.role = role
        self.targets = targets
        self.roles = roles
        self.assign = assign
        let current = targets.first { $0.principalID == role.agentID }
        _agentID = State(initialValue: current?.id ?? targets.first?.id ?? "")
        _sendOnboarding = State(initialValue: !role.onboardingPrompt.isEmpty)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Assign \(role.name)").font(.title2.bold())
            Text("Choose a connected session. Existing role ownership is shown before you move it.")
                .font(.caption).foregroundStyle(.secondary)
            sessionList
            if let occupied = selectedExistingRole, occupied.id != role.id {
                Label(
                    "This will remove \(selectedTargetName) from \(occupied.name) and leave that role unassigned.",
                    systemImage: "exclamationmark.triangle.fill"
                ).font(.caption).foregroundStyle(.orange)
            }
            Toggle("Send saved onboarding prompt once", isOn: $sendOnboarding)
                .disabled(role.onboardingPrompt.isEmpty)
            if !role.onboardingPrompt.isEmpty {
                Text(role.onboardingPrompt).font(.caption).foregroundStyle(.secondary)
                    .lineLimit(5).padding(10).background(.quaternary.opacity(0.3), in: RoundedRectangle(cornerRadius: 8))
            }
            HStack { Spacer(); assignmentButton }
        }.padding(24).frame(width: 520)
            .confirmationDialog(
                "Move \(selectedTargetName) from ‘\(selectedExistingRole?.name ?? "")’ to ‘\(role.name)’?",
                isPresented: $confirmReassignment, titleVisibility: .visible
            ) {
                Button("Move session", role: .destructive) {
                    Task { await assign(agentID, sendOnboarding) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("The previous role becomes unassigned. Its history and messages remain intact.")
            }
    }

    private var sessionList: some View {
        VStack(spacing: 0) {
            ForEach(Array(targets.enumerated()), id: \.element.id) { index, target in
                sessionRow(target)
                if index < targets.count - 1 { Divider() }
            }
        }.background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 9))
    }

    private func sessionRow(_ target: Target) -> some View {
        let currentRole = assignedRole(for: target)
        return Button { agentID = target.id } label: {
            HStack(spacing: 10) {
                Image(systemName: agentID == target.id ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(agentID == target.id ? Color.accentColor : Color.secondary)
                VStack(alignment: .leading, spacing: 3) {
                    Text(target.displayName).foregroundStyle(.primary)
                    HStack(spacing: 5) {
                        Circle().fill(currentRole == nil ? Color.green : Color.orange)
                            .frame(width: 6, height: 6)
                        Text(assignmentLabel(currentRole)).font(.caption)
                            .foregroundStyle(currentRole == nil ? Color.secondary : Color.orange)
                    }
                }
                Spacer()
                Text(target.provider.uppercased()).font(.caption2.bold()).foregroundStyle(.secondary)
            }.padding(10)
        }.buttonStyle(.plain)
    }

    private var assignmentButton: some View {
        Button(assignmentButtonLabel) {
            if let occupied = selectedExistingRole, occupied.id != role.id {
                confirmReassignment = true
            } else {
                Task { await assign(agentID, sendOnboarding) }
            }
        }.buttonStyle(.borderedProminent).disabled(agentID.isEmpty)
    }

    private var assignmentButtonLabel: String {
        if selectedExistingRole?.id == role.id { return "Keep assignment" }
        return selectedExistingRole == nil ? "Assign" : "Reassign"
    }

    private func assignedRole(for target: Target) -> WorkspaceRole? {
        roles.first { $0.agentID == target.principalID }
    }

    private var selectedTarget: Target? { targets.first { $0.id == agentID } }
    private var selectedExistingRole: WorkspaceRole? {
        selectedTarget.flatMap { assignedRole(for: $0) }
    }
    private var selectedTargetName: String { selectedTarget?.displayName ?? "session" }

    private func assignmentLabel(_ assignedRole: WorkspaceRole?) -> String {
        guard let assignedRole else { return "Available · not assigned" }
        return assignedRole.id == role.id
            ? "Currently assigned to this role"
            : "Assigned to \(assignedRole.name)"
    }
}

private struct AssignmentHistoryView: View {
    @EnvironmentObject private var model: AppModel
    let role: WorkspaceRole
    @State private var items: [RoleAssignment] = []

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("\(role.name) assignment history").font(.title2.bold())
            if items.isEmpty {
                Text("No assignment history.").foregroundStyle(.secondary)
            } else {
                List(items) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(item.agentName).font(.headline)
                            Spacer()
                            Text(item.endedAt == nil ? "ACTIVE" : "ENDED")
                                .font(.caption2.bold()).foregroundStyle(item.endedAt == nil ? .green : .secondary)
                        }
                        Text("\(item.assignedAt) → \(item.endedAt ?? "now")")
                            .font(.caption).foregroundStyle(.secondary)
                        if item.onboardingSent {
                            Label("Onboarding sent", systemImage: "paperplane.fill").font(.caption)
                        }
                    }.padding(.vertical, 4)
                }
            }
        }.padding(24).frame(width: 560, height: 440)
            .task { items = await model.roleHistory(id: role.id) }
    }
}
