from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

from app.models.enums import ValidationStatus


@dataclass
class SmilesValidationResult:
    status: ValidationStatus
    is_compound: Optional[bool]
    canonical_smiles: Optional[str]
    error: Optional[str]
    mol: Optional[Chem.Mol]


def validate_and_standardize_smiles(smiles: str | None) -> SmilesValidationResult:
    if smiles is None:
        return SmilesValidationResult(
            status=ValidationStatus.UNPROCESSED,
            is_compound=None,
            canonical_smiles=None,
            error=None,
            mol=None,
        )

    smiles_value = smiles.strip()
    if not smiles_value:
        return SmilesValidationResult(
            status=ValidationStatus.PARSE_FAILED,
            is_compound=False,
            canonical_smiles=None,
            error="Empty SMILES string",
            mol=None,
        )

    try:
        mol = Chem.MolFromSmiles(smiles_value, sanitize=False)
    except Exception as exc:
        return SmilesValidationResult(
            status=ValidationStatus.PARSE_FAILED,
            is_compound=False,
            canonical_smiles=None,
            error=str(exc),
            mol=None,
        )

    if mol is None:
        return SmilesValidationResult(
            status=ValidationStatus.PARSE_FAILED,
            is_compound=False,
            canonical_smiles=None,
            error=f"RDKit could not parse SMILES: {smiles_value}",
            mol=None,
        )

    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:
        return SmilesValidationResult(
            status=ValidationStatus.SANITIZE_FAILED,
            is_compound=False,
            canonical_smiles=None,
            error=str(exc),
            mol=None,
        )

    try:
        standardized = rdMolStandardize.Cleanup(mol)
        standardized = rdMolStandardize.FragmentParent(standardized)
        Chem.SanitizeMol(standardized)
        canonical_smiles = Chem.MolToSmiles(standardized, canonical=True)
    except Exception as exc:
        return SmilesValidationResult(
            status=ValidationStatus.STANDARDIZE_FAILED,
            is_compound=False,
            canonical_smiles=None,
            error=str(exc),
            mol=None,
        )

    return SmilesValidationResult(
        status=ValidationStatus.VALID,
        is_compound=True,
        canonical_smiles=canonical_smiles,
        error=None,
        mol=standardized,
    )
