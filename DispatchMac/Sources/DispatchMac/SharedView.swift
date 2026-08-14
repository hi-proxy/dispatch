import SwiftUI

struct SharedView: View {
    @EnvironmentObject private var model: AppModel
    @State private var editor: SharedValue?
    @State private var adding = false
    @State private var key = ""
    @State private var value = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("Add value", systemImage: "plus") { key = ""; value = ""; adding = true }
                Spacer()
            }.padding(16)
            List(model.snapshot.shared) { item in
                VStack(alignment: .leading, spacing: 5) {
                    HStack {
                        Text(item.key).font(.headline)
                        Text("v\(item.version)").font(.caption).foregroundStyle(.tertiary)
                        Spacer()
                        Button("Edit") { key = item.key; value = item.value; editor = item }
                        Button(role: .destructive) {
                            Task { await model.deleteShared(key: item.key) }
                        } label: { Image(systemName: "trash") }
                    }
                    Text(item.value).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }.padding(.vertical, 6)
            }
        }
        .sheet(isPresented: Binding(get: { adding || editor != nil }, set: { if !$0 { adding = false; editor = nil } })) {
            VStack(alignment: .leading, spacing: 14) {
                Text(editor == nil ? "Add shared value" : "Edit shared value").font(.title2.bold())
                TextField("Key", text: $key).disabled(editor != nil)
                TextEditor(text: $value).frame(height: 180).padding(5)
                    .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 8))
                HStack { Spacer(); Button("Cancel") { adding = false; editor = nil }; Button("Save") {
                    Task { if await model.saveShared(key: key, value: value) { adding = false; editor = nil } }
                }.buttonStyle(.borderedProminent).disabled(key.isEmpty || value.isEmpty) }
            }.padding(24).frame(width: 520)
        }
    }
}
