#!/usr/bin/env python3
"""히트 영역 없는 버튼을 잡는다.

SwiftUI에서 .buttonStyle(.plain)을 쓰면 그려진 픽셀만 눌린다. 여백과 배경은
통과해서, 캡슐이 커 보여도 글자만 눌리는 칩이 된다. contentShape을 주면
도형 전체가 눌린다.

에이전트가 UI를 만들 때 반복해서 빠뜨리는 자리라 기계로 잡는다.
"""
import pathlib
import sys

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "FungisMac/Sources/FungisMac"
WINDOW = 16

def main() -> int:
    missing = []
    for path in sorted(SOURCE.glob("*.swift")):
        lines = path.read_text().splitlines()
        for index, line in enumerate(lines):
            if ".buttonStyle(.plain)" not in line:
                continue
            near = "\n".join(lines[max(0, index - WINDOW):index + 3])
            # 라벨이 별도 타입이면 도형이 그 안에 있다. 검사기가 타입 경계를
            # 못 넘으므로 그 자리에 근거를 적어 둔다.
            if "contentShape" in near or "hit-area:" in near:
                continue
            missing.append(f"{path.name}:{index + 1}")
    if missing:
        print("히트 영역이 없는 버튼:")
        for item in missing:
            print(f"  {item}")
        print("\ncontentShape(Capsule()) 또는 contentShape(Rectangle())을 여백 안쪽에 준다.")
        return 1
    print("모든 plain 버튼에 히트 영역이 있다.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
