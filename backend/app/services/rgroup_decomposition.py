from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from rdkit import Chem
from rdkit.Chem import rdRGroupDecomposition


@dataclass(frozen=True)
class RGroupInput:
    compound_id: int
    patent_id: int
    mol: Chem.Mol


@dataclass(frozen=True)
class RGroupRow:
    compound_id: int
    patent_id: int
    core_smiles: str
    core_smarts: str
    r_label: str
    r_group: str


@dataclass(frozen=True)
class RGroupDecompositionResult:
    core_smiles_by_compound: dict[int, str]
    core_smarts_by_compound: dict[int, str]
    r_groups: list[RGroupRow]
    unmatched_compound_ids: list[int]


def decompose_r_groups(
    *,
    core_smiles: Optional[str],
    compounds: Sequence[RGroupInput],
) -> RGroupDecompositionResult:
    if not core_smiles or not compounds:
        return RGroupDecompositionResult(
            core_smiles_by_compound={},
            core_smarts_by_compound={},
            r_groups=[],
            unmatched_compound_ids=[],
        )

    core = Chem.MolFromSmiles(core_smiles)
    if core is None:
        return RGroupDecompositionResult(
            core_smiles_by_compound={},
            core_smarts_by_compound={},
            r_groups=[],
            unmatched_compound_ids=[item.compound_id for item in compounds],
        )

    rows, unmatched = rdRGroupDecomposition.RGroupDecompose(
        [core],
        [item.mol for item in compounds],
        asRows=True,
    )

    unmatched_indices = set(unmatched)
    matched_compounds = [
        item
        for index, item in enumerate(compounds)
        if index not in unmatched_indices
    ]

    core_smiles_by_compound: dict[int, str] = {}
    core_smarts_by_compound: dict[int, str] = {}
    r_group_rows: list[RGroupRow] = []
    for compound, row in zip(matched_compounds, rows):
        labeled_core = row.get("Core")
        if labeled_core is None:
            continue
        labeled_core_smiles = Chem.MolToSmiles(labeled_core, canonical=True)
        labeled_core_smarts = Chem.MolToSmarts(labeled_core)
        core_smiles_by_compound[compound.compound_id] = labeled_core_smiles
        core_smarts_by_compound[compound.compound_id] = labeled_core_smarts
        for label, fragment in row.items():
            if label == "Core" or fragment is None:
                continue
            r_group_rows.append(
                RGroupRow(
                    compound_id=compound.compound_id,
                    patent_id=compound.patent_id,
                    core_smiles=labeled_core_smiles,
                    core_smarts=labeled_core_smarts,
                    r_label=label,
                    r_group=Chem.MolToSmiles(fragment, canonical=True),
                )
            )

    return RGroupDecompositionResult(
        core_smiles_by_compound=core_smiles_by_compound,
        core_smarts_by_compound=core_smarts_by_compound,
        r_groups=r_group_rows,
        unmatched_compound_ids=[compounds[index].compound_id for index in unmatched],
    )
