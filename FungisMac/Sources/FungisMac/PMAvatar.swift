import SwiftUI

struct PMAvatar: View {
    let profile: PMProfile
    let size: CGFloat

    var body: some View {
        Group {
            if profile.hasAvatar, let url = avatarURL {
                AsyncImage(url: url) { phase in
                    if let image = phase.image { image.resizable().scaledToFill() }
                    else { initials }
                }
            } else { initials }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }

    private var initials: some View {
        ZStack {
            Circle().fill(Color.purple.opacity(0.18))
            Text(String(profile.displayName.prefix(2)).uppercased())
                .font(.system(size: size * 0.34, weight: .bold))
                .foregroundStyle(.purple)
        }
    }

    private var avatarURL: URL? {
        var components = URLComponents(string: "http://127.0.0.1:8790/api/pm-profile/avatar")
        components?.queryItems = [URLQueryItem(name: "v", value: profile.avatarUpdatedAt ?? "0")]
        return components?.url
    }
}
