import SwiftUI

struct RoleAvatar: View {
    let role: WorkspaceRole
    var size: CGFloat = 42

    var body: some View {
        Group {
            if role.hasAvatar, let url = avatarURL {
                AsyncImage(url: url) { phase in
                    if case let .success(image) = phase {
                        image.resizable().scaledToFill()
                    } else {
                        initials
                    }
                }
            } else {
                initials
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().stroke(.white.opacity(0.18), lineWidth: 1))
        .accessibilityLabel("\(role.name) profile")
    }

    private var avatarURL: URL? {
        var components = URLComponents(string: "http://127.0.0.1:8790/api/roles/\(role.id)/avatar")
        components?.queryItems = [URLQueryItem(name: "v", value: role.avatarUpdatedAt ?? "0")]
        return components?.url
    }

    private var initials: some View {
        Text(roleInitials(role.name))
            .font(.system(size: size * 0.36, weight: .bold, design: .rounded))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(roleAvatarColor(role.name))
    }
}

func roleInitials(_ name: String) -> String {
    let words = name.split { !$0.isLetter && !$0.isNumber }
    if words.count >= 2 {
        return String(words.prefix(2).compactMap(\.first)).uppercased()
    }
    return String(name.filter { $0.isLetter || $0.isNumber }.prefix(2)).uppercased()
}

func roleAvatarColor(_ name: String) -> Color {
    let palette: [Color] = [.indigo, .blue, .teal, .purple, .orange, .pink, .green]
    let total = name.unicodeScalars.reduce(0) { $0 + Int($1.value) }
    return palette[total % palette.count]
}
