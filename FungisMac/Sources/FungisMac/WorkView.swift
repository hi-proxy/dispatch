import SwiftUI

struct WorkView: View {
    @EnvironmentObject private var model: AppModel
    private let columns = [GridItem(.adaptive(minimum: 260), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if model.snapshot.work.isEmpty {
                    ContentUnavailableView(
                        "No work reported", systemImage: "clock",
                        description: Text("에이전트가 보고한 작업과 경과 시간이 여기에 쌓입니다.")
                    ).frame(maxWidth: .infinity, minHeight: 240)
                }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(model.snapshot.work) { item in
                        VStack(alignment: .leading, spacing: 10) {
                            HStack { Text(item.agentName).font(.caption.bold()).foregroundStyle(.green); Spacer(); Text(item.status).font(.caption) }
                            Text(item.title).font(.headline)
                            Text(item.lastReport ?? "No report").foregroundStyle(.secondary).frame(minHeight: 40, alignment: .topLeading)
                            Divider()
                            HStack { Label(elapsed(item.elapsedSeconds), systemImage: "clock"); Spacer(); Text("tokens \(item.tokenUsage.map(String.init) ?? "unknown")") }
                                .font(.caption).foregroundStyle(.secondary)
                        }.padding(16).background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
                    }
                }
            }.padding(16)
        }
    }

    private func elapsed(_ value: Int) -> String {
        String(format: "%02d:%02d:%02d", value / 3600, value / 60 % 60, value % 60)
    }
}
