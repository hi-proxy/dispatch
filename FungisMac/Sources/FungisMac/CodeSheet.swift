import SwiftUI

/// 비서가 짚어 준 자리를 보는 창. 읽기 전용이다.
///
/// IDE 로 가지 않는다 — 편집도 검색도 git 통합도 없다. 목적은 코멘트에 적힌
/// 줄을 눈으로 확인하는 것 하나다. 그래야 비서가 코드를 메시지 본문에 베끼지
/// 않아도 되고, 그쪽이 토큰을 훨씬 아낀다.
struct CodeSheet: View {
    let reference: CodeReference
    let projectID: String
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var file: RepositoryFile?
    @State private var painted: [AttributedString] = []
    @State private var failure: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(reference.label).font(.headline).textSelection(.enabled)
                    .foregroundStyle(CodeColors.foreground)
                if let file { origin(of: file) }
                if let file, file.truncated {
                    Text("앞 \(file.lines.count)줄만 · 전체 \(file.totalLines)줄")
                        .font(.caption).foregroundStyle(CodeColors.comment)
                }
                Spacer()
                Button("닫기") { dismiss() }
            }
            .padding(14)
            .background(CodeColors.background)
            Divider()
            content.background(CodeColors.background)
        }
        .frame(width: 900, height: 620)
        .task { await load() }
    }

    @ViewBuilder private var content: some View {
        if let failure {
            VStack(spacing: 10) {
                Image(systemName: "doc.questionmark").font(.largeTitle)
                Text(failure).font(.callout).multilineTextAlignment(.center)
                    .foregroundStyle(CodeColors.comment)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity).padding(30)
        } else if let file {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(painted.enumerated()), id: \.offset) { index, text in
                            line(number: index + 1, text: text)
                        }
                    }.padding(.vertical, 8)
                }
                .onAppear {
                    // 짚어 준 자리를 화면 가운데로. 맨 위에 붙이면 앞뒤
                    // 맥락이 안 보여서 무엇을 고치라는 것인지 알 수 없다.
                    proxy.scrollTo(reference.firstLine, anchor: .center)
                }
            }
        } else {
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    /// 어느 브랜치의 몇 번 커밋인가. 짚어 준 줄이 어느 코드의 줄인지는
    /// 이것 없이 말할 수 없다 — 클라이언트마다 다른 브랜치를 열고 있다.
    @ViewBuilder private func origin(of file: RepositoryFile) -> some View {
        HStack(spacing: 5) {
            if let branch = file.branch {
                Label(branch, systemImage: "arrow.triangle.branch")
            }
            if let head = file.head {
                // 커밋을 실은 참조는 브랜치가 안 온다. 자물쇠가 "이건 움직이는
                // 트리가 아니라 그 커밋" 이라고 말한다.
                if reference.commit != nil {
                    Label(head, systemImage: "lock").monospaced()
                } else {
                    Text(head).monospaced()
                }
            }
            if file.dirty == true {
                // 커밋 안 한 변경이 있으면 이 줄이 그 커밋의 줄이 아닐 수 있다.
                Label("커밋 안 한 변경 있음", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(CodeColors.orange)
            }
        }
        .font(.caption)
        .foregroundStyle(CodeColors.comment)
    }

    private func line(number: Int, text: AttributedString) -> some View {
        let marked = number >= reference.firstLine && number <= reference.lastLine
        return HStack(alignment: .top, spacing: 10) {
            Text("\(number)")
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(marked ? CodeColors.orange : CodeColors.comment)
                .frame(width: 52, alignment: .trailing)
            Text(text.characters.isEmpty ? AttributedString(" ") : text)
                .font(.system(.callout, design: .monospaced))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 12).padding(.vertical, 1)
        // 짚어 준 줄은 한 단계 밝은 바탕으로 깐다. 노란 형광펜을 쓰면
        // 어두운 바탕에서 글자가 죽는다.
        .background(marked ? CodeColors.currentLine : .clear)
        .id(number)
    }

    /// 어느 방의 저장소를 열 것인가. `{{ARCH}}` 뿌리가 붙어 있으면 그 방이고,
    /// 없으면 보고 있는 방이다.
    ///
    /// 뿌리가 없으면 남의 방 코드를 짚을 길이 없다 — 비서는 자기 방에 저장소가
    /// 없어서 어느 방의 코드도 못 가리킨다.
    private var targetProjectID: String? {
        guard let prefix = reference.prefix else { return projectID }
        return model.snapshot.projects.first {
            $0.ticketPrefix?.caseInsensitiveCompare(prefix) == .orderedSame
        }?.id
    }

    private func load() async {
        guard let target = targetProjectID else {
            failure = "{{\(reference.prefix ?? "")}} 라는 방이 없다"
            return
        }
        do {
            let seen = try await model.api.file(
                projectID: target, path: reference.path, ref: reference.commit
            )
            painted = CodeHighlighter.paint(lines: seen.lines, path: seen.path)
            file = seen
        } catch {
            failure = error.localizedDescription
        }
    }
}

/// 메시지에 딸린 코드 자리 단추들. 없으면 아무것도 안 그린다.
///
/// MessageRow 본문에 인라인으로 두면 그 뷰의 타입 검사가 한계를 넘는다.
/// 별도 뷰로 떼는 것이 여기서는 취향이 아니라 컴파일 조건이다.
struct CodeReferenceRow: View {
    let references: [CodeReference]
    let open: (CodeReference) -> Void

    var body: some View {
        if !references.isEmpty {
            HStack(spacing: 6) {
                ForEach(references) { reference in
                    Button { open(reference) } label: {
                        Label(
                            reference.label,
                            systemImage: "chevron.left.forwardslash.chevron.right"
                        )
                        .font(.caption2).lineLimit(1)
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(.quaternary.opacity(0.5), in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .help("이 자리를 연다")
                }
            }
        }
    }
}
