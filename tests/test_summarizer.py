from agents.summarizer import clamp_key_points


def test_clamp_trims_to_three():
    s = {"keyPoints": ["a", "b", "c", "d", "e"]}
    assert clamp_key_points(s)["keyPoints"] == ["a", "b", "c"]


def test_clamp_leaves_three():
    s = {"keyPoints": ["a", "b", "c"]}
    assert clamp_key_points(s)["keyPoints"] == ["a", "b", "c"]


def test_clamp_leaves_fewer():
    s = {"keyPoints": ["a"]}
    assert clamp_key_points(s)["keyPoints"] == ["a"]


def test_clamp_missing_key_noop():
    s = {"title": "t"}
    assert clamp_key_points(s) == {"title": "t"}


def test_clamp_non_list_noop():
    s = {"keyPoints": "not a list"}
    assert clamp_key_points(s)["keyPoints"] == "not a list"
