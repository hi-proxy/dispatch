import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @State private var search = ""
    @State private var showAgents = false
    @State private var creatingProject = false
    @State private var renamingProject: DispatchProject?
    @State private var projectName = ""
    @State private var repositoryProject: DispatchProject?
    @State private var choosingRepository = false

    var body: some View {
        NavigationSplitView {
            ScrollView {
                LazyVStack(spacing: 2) {
                    ForEach(filteredProjects) { project in
                        Button {
                            model.selectProject(project.id)
                        } label: {
                            ProjectRow(
                                project: project,
                                repository: repository(for: project.id),
                                selected: project.id == model.selectedProjectID
                            )
                        }
                        .buttonStyle(.plain)
                        .contextMenu { projectMenu(project) }
                    }
                }.padding(.horizontal, 8)
            }
            .navigationSplitViewColumnWidth(min: 220, ideal: 260, max: 360)
            .safeAreaInset(edge: .top) { searchField }
            .safeAreaInset(edge: .bottom) { statusBar }
            .toolbar {
                ToolbarItem {
                    Button {
                        projectName = ""
                        creatingProject = true
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }.help("New project")
                }
            }
        } detail: {
            ChatView()
                .navigationTitle(selectedProjectName)
                .navigationSubtitle("\(model.snapshot.roles.count + 1) participants")
                .overlay(alignment: .bottom) {
                    if let error = model.errorMessage {
                        Text(error).font(.caption).padding(.horizontal, 12).padding(.vertical, 8)
                            .background(.red.opacity(0.9), in: Capsule()).foregroundStyle(.white)
                            .padding()
                    }
                }
        }
        .sheet(isPresented: $showAgents) {
            AgentsView().frame(minWidth: 720, minHeight: 460)
        }
        .sheet(isPresented: $creatingProject) {
            projectEditor(title: "New project") {
                if await model.createProject(name: projectName) { creatingProject = false }
            }
        }
        .sheet(item: $renamingProject) { project in
            projectEditor(title: "Rename project") {
                if await model.updateProject(id: project.id, name: projectName) {
                    renamingProject = nil
                }
            }
        }
        .fileImporter(
            isPresented: $choosingRepository,
            allowedContentTypes: [.folder], allowsMultipleSelection: false
        ) { result in
            guard let project = repositoryProject,
                  case let .success(urls) = result, let url = urls.first else { return }
            let accessing = url.startAccessingSecurityScopedResource()
            let path = url.path
            if accessing { url.stopAccessingSecurityScopedResource() }
            Task { _ = await model.setProjectRepository(projectID: project.id, path: path) }
        }
    }

    /// `.searchable(placement: .sidebar)`는 좁은 사이드바에서 돋보기 버튼으로 접히므로
    /// 항상 보이는 필드를 직접 둔다.
    private var searchField: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass").font(.caption).foregroundStyle(.secondary)
            TextField("Search", text: $search)
                .textFieldStyle(.plain).font(.callout)
            if !search.isEmpty {
                Button { search = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(.tertiary)
                }.buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 8).padding(.vertical, 5)
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 7))
        .padding(.horizontal, 10).padding(.bottom, 8)
    }

    private var statusBar: some View {
        VStack(spacing: 0) {
            Divider()
            Button {
                showAgents = true
            } label: {
                HStack(spacing: 7) {
                    Circle()
                        .fill(model.isConnected ? Color.green : Color.red)
                        .frame(width: 7, height: 7)
                    Text(agentSummary).font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    Image(systemName: "chevron.up").font(.caption2).foregroundStyle(.tertiary)
                }
                .contentShape(Rectangle())
                .padding(.horizontal, 14).padding(.vertical, 9)
            }
            .buttonStyle(.plain)
            .help("Agent sessions")
        }
        .background(.bar)
    }

    private var agentSummary: String {
        guard model.isConnected else { return "Disconnected" }
        let online = model.snapshot.targets.filter { target in
            let lifecycle = model.snapshot.statuses.first { $0.id == target.id }?.lifecycle
                ?? target.lifecycle
            return lifecycle != "unknown"
        }.count
        return online == 0 ? "No agents online" : "\(online) agents online"
    }

    private var filteredProjects: [DispatchProject] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return model.snapshot.projects }
        return model.snapshot.projects.filter {
            $0.name.localizedCaseInsensitiveContains(query)
        }
    }

    private var selectedProjectName: String {
        model.snapshot.projects.first { $0.id == model.selectedProjectID }?.name ?? "Dispatch"
    }

    private func repository(for projectID: String) -> ProjectRepository? {
        model.snapshot.projectRepositories.first { $0.projectID == projectID }
    }

    @ViewBuilder
    private func projectMenu(_ project: DispatchProject) -> some View {
        Button("Rename…") { projectName = project.name; renamingProject = project }
        Button(repository(for: project.id) == nil ? "Choose repository…" : "Change repository…") {
            repositoryProject = project
            choosingRepository = true
        }
        if repository(for: project.id) != nil {
            Button("Remove repository", role: .destructive) {
                Task { _ = await model.deleteProjectRepository(projectID: project.id) }
            }
        }
    }

    private func projectEditor(title: String, save: @escaping () async -> Void) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(title).font(.title2.bold())
            TextField("Project name", text: $projectName)
            HStack {
                Spacer()
                Button("Save") { Task { await save() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(
                        projectName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
            }
        }.padding(24).frame(width: 420)
    }
}

private struct ProjectRow: View {
    let project: DispatchProject
    let repository: ProjectRepository?
    let selected: Bool

    var body: some View {
        HStack(spacing: 10) {
            Text(roleInitials(project.name))
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .frame(width: 34, height: 34)
                .background(roleAvatarColor(project.name), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(project.name).font(.body.weight(.medium)).lineLimit(1)
                Text(subtitle).font(.caption)
                    .foregroundStyle(selected ? .white.opacity(0.75) : .secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .foregroundStyle(selected ? .white : .primary)
        .padding(.horizontal, 8).padding(.vertical, 6)
        .background(
            selected ? Color.accentColor : .clear,
            in: RoundedRectangle(cornerRadius: 8)
        )
        .contentShape(RoundedRectangle(cornerRadius: 8))
    }

    private var subtitle: String {
        guard let repository else { return "No repository" }
        guard let git = repository.git else { return repository.path }
        return (git.branch ?? "detached HEAD") + (git.dirty ? " · dirty" : "")
    }
}

func statusColor(_ lifecycle: String) -> Color {
    switch lifecycle {
    case "running": .blue
    case "idle", "needs_input": .green
    default: .gray
    }
}
