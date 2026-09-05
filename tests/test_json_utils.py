import json

import pytest

from agents.json_utils import parse_json

OBJ = {"title": "T", "keyPoints": ["a", "b", "c"], "takeaway": "x"}


def test_plain_json():
    assert parse_json(json.dumps(OBJ)) == OBJ


def test_leading_trailing_whitespace():
    assert parse_json("  \n" + json.dumps(OBJ) + "\n  ") == OBJ


def test_json_fence():
    raw = "```json\n" + json.dumps(OBJ) + "\n```"
    assert parse_json(raw) == OBJ


def test_bare_fence():
    raw = "```\n" + json.dumps(OBJ) + "\n```"
    assert parse_json(raw) == OBJ


def test_prose_around_object():
    raw = "Here is the JSON you asked for:\n" + json.dumps(OBJ) + "\nHope that helps!"
    assert parse_json(raw) == OBJ


def test_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json("this is not json at all")


def test_empty_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json("")
