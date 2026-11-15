import json

from src.vision.json_repair import find_json_object, parse_vision_output, remove_trailing_commas

GOOD = {"damages": [{"part": "bonnet", "damage_type": "dent", "severity": "minor", "confidence": 0.6,
                     "image_index": 0, "notes": "small dent"}], "image_quality_flags": []}


def test_plain_json_parses():
    result = parse_vision_output(json.dumps(GOOD), num_images=1)
    assert result.ok and result.output.damages[0].part == "bonnet"


def test_json_inside_code_fence_with_prose_parses():
    text = "Here is my assessment:\n```json\n" + json.dumps(GOOD) + "\n```\nLet me know if you need more."
    assert parse_vision_output(text, num_images=1).ok


def test_think_block_is_ignored():
    text = "<think>maybe {not json}</think>" + json.dumps(GOOD)
    assert parse_vision_output(text, num_images=1).ok


def test_last_object_wins_when_reasoning_precedes_answer():
    text = 'I considered {"damages": "draft"} first. Final: ' + json.dumps(GOOD)
    assert find_json_object(text) == json.dumps(GOOD)


def test_braces_inside_strings_do_not_confuse_the_scanner():
    payload = {**GOOD, "damages": [{**GOOD["damages"][0], "notes": "odd {brace} in notes"}]}
    assert parse_vision_output(json.dumps(payload), num_images=1).ok


def test_trailing_commas_are_removed():
    assert json.loads(remove_trailing_commas('{"a": [1, 2,], }')) == {"a": [1, 2]}
    text = '{"damages": [], "image_quality_flags": [],}'
    assert parse_vision_output(text, num_images=1).ok


def test_prose_only_reply_reports_missing_json():
    result = parse_vision_output("The front bumper has a large dent.", num_images=1)
    assert not result.ok and "no JSON object" in result.error


def test_broken_json_reports_parse_error():
    result = parse_vision_output('{"damages": [ {"part": "bonnet" ', num_images=1)
    assert not result.ok


def test_schema_violation_lists_the_field():
    bad = {"damages": [{**GOOD["damages"][0], "part": "headlight"}], "image_quality_flags": []}
    result = parse_vision_output(json.dumps(bad), num_images=1)
    assert not result.ok and "damages.0.part" in result.error


def test_image_index_beyond_photo_count_is_rejected():
    bad = {"damages": [{**GOOD["damages"][0], "image_index": 2}], "image_quality_flags": ["image_3_blurry"]}
    result = parse_vision_output(json.dumps(bad), num_images=2)
    assert not result.ok and "[2]" in result.error and "image_3_blurry" in result.error


def test_top_level_array_is_rejected():
    assert not parse_vision_output("[1, 2]", num_images=1).ok
