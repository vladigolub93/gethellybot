PHRASE_WORDS_ONE = (
    "north",
    "silver",
    "bright",
    "rapid",
    "clear",
    "steady",
    "open",
    "strong",
)

PHRASE_WORDS_TWO = (
    "signal",
    "bridge",
    "planet",
    "harbor",
    "rocket",
    "forest",
    "anchor",
    "vector",
)


def build_verification_phrase(*, profile_id, attempt_no: int) -> str:
    seed = str(profile_id).replace("-", "")
    first_index = int(seed[:4], 16) % len(PHRASE_WORDS_ONE)
    second_index = int(seed[-4:], 16) % len(PHRASE_WORDS_TWO)
    return f"Helly verification {attempt_no}: {PHRASE_WORDS_ONE[first_index]} {PHRASE_WORDS_TWO[second_index]}"
