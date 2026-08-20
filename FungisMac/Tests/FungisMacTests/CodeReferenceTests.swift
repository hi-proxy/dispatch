import Foundation
import Testing
@testable import FungisMac

@Test func findsFileAndLineTheWayTheSecretaryWritesIt() {
    // 비서에게 코드를 인용하지 말고 이 형식으로 쓰라고 정했다.
    let found = CodeReference.found(in: """
    fungis_node/inbox.py:68
    읽을 것이 없을 때 깨우기를 안 지운다

    FungisMac/Sources/FungisMac/ChatView.swift:734-742
    같은 초안이 두 번 나간다
    """)
    #expect(found.count == 2)
    #expect(found[0].label == "fungis_node/inbox.py:68")
    #expect(found[0].firstLine == 68 && found[0].lastLine == 68)
    #expect(found[1].label == "FungisMac/Sources/FungisMac/ChatView.swift:734-742")
    #expect(found[1].lastLine == 742)
}

@Test func doesNotTurnEverydayNumbersIntoFiles() {
    // 확장자를 요구하지 않으면 방 번호와 시각이 전부 파일로 잡힌다.
    // 타임라인이 눌리지도 않는 단추로 뒤덮인다.
    #expect(CodeReference.found(in: "fungis reply 42 로 답한다").isEmpty)
    #expect(CodeReference.found(in: "#397:1 을 보라").isEmpty)
    #expect(CodeReference.found(in: "15:44:49 에 도착했다").isEmpty)
    #expect(CodeReference.found(in: "커밋 1294aa1 을 봐라").isEmpty)
}

@Test func aRootPointsAtAnotherRoomsRepository() {
    // 뿌리가 없으면 남의 방 코드를 짚을 길이 없다. 비서는 자기 방에 저장소가
    // 없어서 어느 방의 코드도 못 가리킨다.
    let found = CodeReference.found(in: "{{ARCH}}/lib/src/index.dart:33-35 을 봐라")
    #expect(found.count == 1)
    #expect(found[0].prefix == "ARCH")
    #expect(found[0].path == "lib/src/index.dart")
    #expect(found[0].firstLine == 33 && found[0].lastLine == 35)
    #expect(found[0].label == "ARCH lib/src/index.dart:33-35")
}

@Test func aReferenceCanCarryTheCommit() {
    // 짚은 쪽과 보는 쪽이 다른 브랜치를 열고 있으면 같은 줄이 다른 코드다.
    let found = CodeReference.found(in: "{{FUNG}}/fungis_node/inbox.py@23927f6:68")
    #expect(found.count == 1)
    #expect(found[0].prefix == "FUNG")
    #expect(found[0].path == "fungis_node/inbox.py")
    #expect(found[0].commit == "23927f6")
    #expect(found[0].firstLine == 68)

    // 뿌리 없이 커밋만 실어도 된다. 그 방 안에서 옛 줄을 짚는 경우다.
    let here = CodeReference.found(in: "web.py@a1b2c3d4e5:10-12")
    #expect(here.first?.prefix == nil)
    #expect(here.first?.commit == "a1b2c3d4e5")
    #expect(here.first?.lastLine == 12)
}

@Test func aPlainSpotStillHasNoRootAndNoCommit() {
    // 옛 형식이 그대로 열려야 한다. 오늘 이전에 오간 참조가 전부 그 모양이다.
    let found = CodeReference.found(in: "db.py:601")
    #expect(found.first?.prefix == nil)
    #expect(found.first?.commit == nil)
    #expect(found.first?.label == "db.py:601")
}

@Test func theSameSpotIsListedOnce() {
    let found = CodeReference.found(in: "db.py:601 과 db.py:601 은 같은 자리다")
    #expect(found.count == 1)
}

@Test func aBackwardRangeDoesNotInvert() {
    // 잘못 적어도 첫 줄보다 앞으로 가지 않는다.
    let found = CodeReference.found(in: "web.py:100-20")
    #expect(found.first?.firstLine == 100)
    #expect(found.first?.lastLine == 100)
}
