from __future__ import annotations

from app.models.enums import ValidationStatus
from app.services.smiles_validation import validate_and_standardize_smiles


def test_validate_and_standardize_smiles_accepts_valid_smiles():
    result = validate_and_standardize_smiles("CCO")

    assert result.status == ValidationStatus.VALID
    assert result.is_compound is True
    assert result.canonical_smiles == "CCO"
    assert result.error is None


def test_validate_and_standardize_smiles_leaves_none_unprocessed():
    result = validate_and_standardize_smiles(None)

    assert result.status == ValidationStatus.UNPROCESSED
    assert result.is_compound is None
    assert result.canonical_smiles is None


def test_validate_and_standardize_smiles_marks_blank_smiles_as_non_compound():
    result = validate_and_standardize_smiles("   ")

    assert result.status == ValidationStatus.PARSE_FAILED
    assert result.is_compound is False
    assert result.canonical_smiles is None
    assert "Empty SMILES" in (result.error or "")


def test_validate_and_standardize_smiles_marks_unparsable_smiles_as_non_compound():
    result = validate_and_standardize_smiles("not-a-smiles")

    assert result.status == ValidationStatus.PARSE_FAILED
    assert result.is_compound is False
    assert result.canonical_smiles is None


def test_validate_and_standardize_smiles_marks_sanitize_failures_as_non_compound():
    result = validate_and_standardize_smiles("C[N](C)(C)C")

    assert result.status == ValidationStatus.SANITIZE_FAILED
    assert result.is_compound is False
    assert result.canonical_smiles is None


def test_validate_and_standardize_smiles_canonicalizes_deterministically():
    first = validate_and_standardize_smiles("OCC")
    second = validate_and_standardize_smiles("CCO.Cl")

    assert first.status == ValidationStatus.VALID
    assert second.status == ValidationStatus.VALID
    assert first.canonical_smiles == "CCO"
    assert second.canonical_smiles == "CCO"
