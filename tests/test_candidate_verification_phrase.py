from src.candidate_profile.verification import (
    build_verification_phrase,
    format_verification_transcript_hint,
    phrase_matches_verification,
)


def test_build_verification_phrase_uses_it_friendly_phrase(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.candidate_profile.verification.secrets.choice",
        lambda phrases: "green deploy",
    )

    phrase = build_verification_phrase(profile_id="ignored", attempt_no=1)

    assert phrase == "Helly check: green deploy"


def test_build_verification_phrase_is_not_attempt_based_literal() -> None:
    phrase = build_verification_phrase(profile_id="ignored", attempt_no=7)

    assert phrase.startswith("Helly check: ")
    assert "verification 7" not in phrase.lower()


def test_phrase_matches_verification_accepts_normalized_match() -> None:
    assert phrase_matches_verification(
        expected_phrase="Helly check: sync complete",
        spoken_text="helly check sync complete",
    )


def test_phrase_matches_verification_rejects_wrong_phrase() -> None:
    assert not phrase_matches_verification(
        expected_phrase="Helly check: sync complete",
        spoken_text="helly check green deploy",
    )


def test_phrase_matches_verification_accepts_fuzzy_short_phrase() -> None:
    assert phrase_matches_verification(
        expected_phrase="Helly check: prod is green",
        spoken_text="helly check product green",
    )


def test_format_verification_transcript_hint_returns_user_facing_text() -> None:
    assert format_verification_transcript_hint("helly check prod is green") == (
        'What I heard: "helly check prod is green"'
    )
