"""Unit tests for the conservative material-disagreement helper."""

from __future__ import annotations

from app.services.evidence_conflict import (
    claim_is_verbatim,
    claims_materially_disagree,
)


def test_verbatim_claim_ignores_whitespace_case_and_terminal_punctuation():
    source = "The property has 3 floors.\nThe owner is Ananya Rao."

    assert claim_is_verbatim("the property has 3 floors", source)
    assert claim_is_verbatim("The owner is Ananya Rao.", source)
    assert not claim_is_verbatim("The property has 4 floors.", source)


def test_numeric_mismatch_on_a_shared_subject_is_detected():
    disagrees, reason = claims_materially_disagree(
        "The property has 3 floors.",
        "The property has 4 floors.",
    )

    assert disagrees is True
    assert "numeric" in reason


def test_opposite_polarity_on_a_shared_subject_is_detected():
    disagrees, reason = claims_materially_disagree(
        "There are no outstanding loans or mortgages on the property.",
        "An active mortgage loan is registered on the property.",
    )

    assert disagrees is True
    assert "polarity" in reason


def test_unrelated_numbers_do_not_create_a_conflict():
    disagrees, _ = claims_materially_disagree(
        "The property is at 14 Rosewood Layout.",
        "The sale deed is dated 12 January 2024.",
    )

    assert disagrees is False


def test_generic_title_language_is_not_treated_as_a_conflict():
    disagrees, _ = claims_materially_disagree(
        "This sale deed records that the title is free from encumbrance.",
        "The title chain records a sale deed from M. Krishnan in 2024.",
    )

    assert disagrees is False


def test_different_scope_is_not_treated_as_a_material_conflict():
    disagrees, _ = claims_materially_disagree(
        "The property has 3 floors and a garden.",
        "The property has 3 floors and a pool.",
    )

    assert disagrees is False


def test_corroborating_claims_do_not_create_conflict():
    disagrees, reason = claims_materially_disagree(
        "The property has 3 floors.",
        "The property has 3 floors.",
    )

    assert disagrees is False
    assert "no verifiable material disagreement" in reason


def test_antonym_pairs_detected_as_material_conflict():
    disagrees, reason = claims_materially_disagree(
        "The building plan was approved by the municipal authority.",
        "The building plan was rejected by the municipal authority.",
    )

    assert disagrees is True
    assert "opposing terms" in reason
