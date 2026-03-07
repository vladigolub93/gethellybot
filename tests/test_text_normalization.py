from src.shared.text import normalize_command_text


def test_normalize_command_text_strips_case_whitespace_and_trailing_punctuation() -> None:
    assert normalize_command_text("  Approve summary!!!  ") == "approve summary"
