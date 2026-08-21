import Testing
@testable import FungisMac

@Test func contextMetadataKeepsEverythingOnlyAtFullDensity() {
    let plan = ContextMetadataPlan.make(
        density: .full, hasTrack: true, tagCount: 4, detectedCount: 3
    )

    #expect(plan.visibleTagCount == 4)
    #expect(plan.visibleDetectedCount == 3)
}

@Test func contextMetadataKeepsOneManualTagAtMediumDensity() {
    let plan = ContextMetadataPlan.make(
        density: .medium, hasTrack: true, tagCount: 4, detectedCount: 3
    )

    #expect(plan.visibleTagCount == 1)
    #expect(plan.visibleDetectedCount == 0)
    #expect(4 - plan.visibleTagCount + 3 - plan.visibleDetectedCount == 6)
}

@Test func compactMetadataPrioritizesTrackOverTags() {
    let withTrack = ContextMetadataPlan.make(
        density: .compact, hasTrack: true, tagCount: 4, detectedCount: 3
    )
    let withoutTrack = ContextMetadataPlan.make(
        density: .compact, hasTrack: false, tagCount: 4, detectedCount: 3
    )

    #expect(withTrack.visibleTagCount == 0)
    #expect(withoutTrack.visibleTagCount == 1)
    #expect(withTrack.visibleDetectedCount == 0)
}
