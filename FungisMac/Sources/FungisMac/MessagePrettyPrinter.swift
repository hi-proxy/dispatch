import SwiftUI

enum MessagePrettyPrinter {
    private static let lineBreakMarkers = Set(
        "■□●○◆◇▪▫①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳✓✔✅☑✗✕❌"
    )

    static func format(_ source: String) -> String {
        let normalized = source
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
        var result = ""
        var isAtLineStart = true

        for character in normalized {
            // 목록 머리표일 때만 줄을 나눈다. 앞이 공백이 아니면 본문 안에
            // 쓰인 기호다. ③①②처럼 잇달아 적거나 (③→①→②)처럼 괄호 안에
            // 넣은 것을 쪼개면 원문이 뜻하는 바가 망가진다.
            let followsSpace = result.last == " " || result.last == "\t"
            if lineBreakMarkers.contains(character), !isAtLineStart, followsSpace {
                while result.last == " " || result.last == "\t" {
                    result.removeLast()
                }
                if result.last != "\n" {
                    result.append("\n")
                }
                isAtLineStart = true
            }

            result.append(character)
            isAtLineStart = character == "\n"
        }

        return result
    }

    static func prettyText(_ source: String, seed: Int) -> AttributedString {
        let formatted = format(source)
        var result = AttributedString()
        var cursor = formatted.startIndex
        var highlightIndex = 0

        while let opening = formatted.range(of: "**", range: cursor..<formatted.endIndex) {
            result.append(AttributedString(String(formatted[cursor..<opening.lowerBound])))
            guard let closing = formatted.range(
                of: "**", range: opening.upperBound..<formatted.endIndex
            ) else {
                result.append(AttributedString(String(formatted[opening.lowerBound...])))
                return result
            }

            let content = String(formatted[opening.upperBound..<closing.lowerBound])
            if content.isEmpty {
                result.append(AttributedString("****"))
            } else {
                var highlighted = AttributedString(content)
                highlighted.backgroundColor = highlighterColor(
                    content: content, seed: seed + highlightIndex
                )
                highlighted.foregroundColor = Color.black.opacity(0.82)
                result.append(highlighted)
                highlightIndex += 1
            }
            cursor = closing.upperBound
        }

        result.append(AttributedString(String(formatted[cursor...])))
        return result
    }

    private static func highlighterColor(content: String, seed: Int) -> Color {
        let palette: [Color] = [
            Color(red: 1.00, green: 0.88, blue: 0.30),
            Color(red: 0.56, green: 0.93, blue: 0.70),
            Color(red: 1.00, green: 0.66, blue: 0.47),
            Color(red: 0.98, green: 0.62, blue: 0.78),
            Color(red: 0.50, green: 0.86, blue: 0.95),
        ]
        let scalarTotal = content.unicodeScalars.reduce(seed.magnitude) {
            $0 &+ UInt($1.value)
        }
        return palette[Int(scalarTotal % UInt(palette.count))].opacity(0.78)
    }
}
