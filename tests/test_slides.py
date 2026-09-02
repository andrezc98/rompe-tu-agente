"""Guards on the speaker-facing deck: structure, timing budget, neutral Spanish, filled data slots."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONTENIDO = REPO / "slides" / "contenido.md"
CHAOS_V2 = REPO / "evals" / "results" / "chaos-v2.json"

FIELDS = ("**Headline:**", "**Body:**", "**Layout sugerido:**", "**Notas del orador:**")
SLIDE_HEADING = re.compile(r"^## Slide (\d{2}) — .+$", re.MULTILINE)
TIMING = re.compile(r"\(~(\d+) s\)")

# Word boundaries, not plain substrings: "decía" contains "decí" and "casos " contains "sos ".
VOSEO = re.compile(
    r"\b(respondé|decí|decilo|sabés|podés|tenés|sos|vos)\b", re.IGNORECASE
)

TOTAL_MIN_S = 1680  # 28 min
TOTAL_MAX_S = 1800  # 30 min


@pytest.fixture(scope="module")
def text() -> str:
    return CONTENIDO.read_text()


def slides(text: str) -> list[str]:
    """Split the file into one chunk per slide, dropping the preamble."""
    return re.split(r"^## Slide ", text, flags=re.MULTILINE)[1:]


def test_exactly_25_slides_numbered_in_order(text):
    numbers = SLIDE_HEADING.findall(text)
    assert numbers == [f"{i:02d}" for i in range(1, 26)]


def test_every_slide_has_the_four_fields(text):
    for chunk in slides(text):
        title = chunk.splitlines()[0]
        for field in FIELDS:
            assert field in chunk, f"slide '{title}' is missing {field}"


def test_one_timing_per_slide_and_total_between_28_and_30_minutes(text):
    per_slide = [TIMING.findall(chunk) for chunk in slides(text)]
    assert all(len(found) == 1 for found in per_slide), "each slide needs exactly one (~NN s)"
    total = sum(int(found[0]) for found in per_slide)
    assert TOTAL_MIN_S <= total <= TOTAL_MAX_S, f"deck runs {total} s"


def test_no_voseo(text):
    assert VOSEO.findall(text) == []


def test_no_unfilled_data_slots_once_the_runs_exist(text):
    if not CHAOS_V2.exists():
        pytest.skip(f"pass B not run yet: {CHAOS_V2} does not exist")
    slots = re.findall(r"\[DATO:[^\]]*\]", text)
    assert slots == [], f"{len(slots)} unfilled slots, first: {slots[0]}"
