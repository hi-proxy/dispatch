import Testing
@testable import DispatchMac

@Test func insertsLineBreaksBeforeStructureMarkers() {
    let source = "요약 ■첫 항목 ①세부 내용 ✓완료"

    #expect(MessagePrettyPrinter.format(source) == "요약\n■첫 항목\n①세부 내용\n✓완료")
}

@Test func preservesExistingLinesAndLeadingMarkers() {
    let source = "■첫 줄\n②둘째 줄\n일반 문장"

    #expect(MessagePrettyPrinter.format(source) == source)
}

@Test func rawSourceRemainsAvailableWithoutFormatting() {
    let source = "한 줄 ■원문"

    #expect(source == "한 줄 ■원문")
    #expect(MessagePrettyPrinter.format(source) != source)
}

@Test func convertsDoubleAsterisksToStableHighlighterRuns() {
    let source = "결론 **승인 필요** 다음 **주의**"
    let first = MessagePrettyPrinter.prettyText(source, seed: 42)
    let second = MessagePrettyPrinter.prettyText(source, seed: 42)

    #expect(String(first.characters) == "결론 승인 필요 다음 주의")
    #expect(first == second)
    #expect(first.runs.contains { $0.backgroundColor != nil })
}

@Test func preservesAnUnclosedHighlightMarker() {
    let source = "아직 **미완성"

    #expect(String(MessagePrettyPrinter.prettyText(source, seed: 1).characters) == source)
}
