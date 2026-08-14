from dispatch_node.context_detection import detect_contexts


def test_detects_only_verified_branch_and_commit():
    contexts = [{
        "branches": ["main", "feature/dispatch-tracks"],
        "head": "abcdef123456",
    }]
    found = detect_contexts(
        "feature/dispatch-tracks에서 ARC-42를 abcdef1로 검증", contexts,
        verified_commits={"abcdef1"},
    )
    assert found == [
        {"kind": "branch", "value": "feature/dispatch-tracks", "verified": True},
        {"kind": "commit", "value": "abcdef1", "verified": True},
    ]


def test_does_not_match_branch_embedded_in_another_word_or_random_words():
    contexts = [{"branches": ["main"], "head": "abcdef123456"}]
    assert detect_contexts("domain is maintained", contexts) == []


def test_generic_branch_requires_explicit_marker_and_unknown_hash_is_ignored():
    contexts = [{"branches": ["main"], "head": "abcdef123456"}]
    assert detect_contexts("main에서 deadbee 확인", contexts) == []
    assert detect_contexts("branch:main에서 확인", contexts) == [
        {"kind": "branch", "value": "main", "verified": True},
    ]
