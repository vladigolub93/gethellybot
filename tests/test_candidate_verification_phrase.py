from src.candidate_profile.verification import build_verification_phrase


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
