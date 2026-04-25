from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from rdkit import Chem
from rdkit.Chem import BRICS
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold


@dataclass(frozen=True)
class ScaffoldInput:
    compound_id: int
    mol: Chem.Mol


@dataclass(frozen=True)
class ScaffoldAssignment:
    compound_id: int
    murcko_scaffold_smiles: Optional[str]
    reduced_core: Optional[str]
    scaffold_count: int


@dataclass(frozen=True)
class ReducedCoreCandidate:
    smiles: str
    ring_count: int
    atom_count: int
    hetero_atom_count: int


def _murcko_scaffold(mol: Chem.Mol) -> Optional[Chem.Mol]:
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        return None
    try:
        Chem.SanitizeMol(scaffold)
    except Exception:
        return None
    return scaffold


def _candidate_from_mol(mol: Chem.Mol) -> Optional[ReducedCoreCandidate]:
    if mol.GetNumAtoms() == 0 or rdMolDescriptors.CalcNumRings(mol) <= 0:
        return None
    smiles = Chem.MolToSmiles(mol, canonical=True)
    if not smiles:
        return None
    hetero_atom_count = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in {1, 6})
    return ReducedCoreCandidate(
        smiles=smiles,
        ring_count=rdMolDescriptors.CalcNumRings(mol),
        atom_count=mol.GetNumHeavyAtoms(),
        hetero_atom_count=hetero_atom_count,
    )


def _pick_reduced_core(scaffold: Chem.Mol) -> str:
    candidate_by_smiles: dict[str, ReducedCoreCandidate] = {}
    bond_ids: set[int] = set()
    for atom_pair, _ in BRICS.FindBRICSBonds(scaffold):
        bond = scaffold.GetBondBetweenAtoms(*atom_pair)
        if bond is not None:
            bond_ids.add(bond.GetIdx())

    for bond_id in bond_ids:
        fragmented = Chem.FragmentOnBonds(scaffold, [bond_id], addDummies=False)
        for fragment in Chem.GetMolFrags(fragmented, asMols=True, sanitizeFrags=True):
            candidate = _candidate_from_mol(fragment)
            if candidate is not None:
                candidate_by_smiles[candidate.smiles] = candidate

    if not candidate_by_smiles:
        return Chem.MolToSmiles(scaffold, canonical=True)

    return max(
        candidate_by_smiles.values(),
        key=lambda candidate: (
            candidate.ring_count,
            -candidate.atom_count,
            candidate.hetero_atom_count,
            candidate.smiles,
        ),
    ).smiles


def analyze_scaffolds(
    compounds: Sequence[ScaffoldInput],
) -> dict[int, ScaffoldAssignment]:
    scaffold_by_compound: dict[int, Optional[str]] = {}
    reduced_core_by_compound: dict[int, Optional[str]] = {}
    for item in compounds:
        scaffold = _murcko_scaffold(item.mol)
        if scaffold is None:
            scaffold_by_compound[item.compound_id] = None
            reduced_core_by_compound[item.compound_id] = None
            continue

        scaffold_smiles = Chem.MolToSmiles(scaffold, canonical=True) or None
        scaffold_by_compound[item.compound_id] = scaffold_smiles
        reduced_core_by_compound[item.compound_id] = _pick_reduced_core(scaffold) if scaffold_smiles else None

    scaffold_counts: dict[str, int] = {}
    for smiles in scaffold_by_compound.values():
        if smiles:
            scaffold_counts[smiles] = scaffold_counts.get(smiles, 0) + 1

    assignments: dict[int, ScaffoldAssignment] = {}
    for item in compounds:
        scaffold_smiles = scaffold_by_compound[item.compound_id]
        scaffold_count = scaffold_counts.get(scaffold_smiles, 0) if scaffold_smiles else 0

        assignments[item.compound_id] = ScaffoldAssignment(
            compound_id=item.compound_id,
            murcko_scaffold_smiles=scaffold_smiles,
            reduced_core=reduced_core_by_compound[item.compound_id],
            scaffold_count=scaffold_count,
        )

    return assignments
