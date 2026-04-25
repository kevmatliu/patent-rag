from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem

from app.core.logging import get_logger
from app.services.rgroup_decomposition import RGroupInput, decompose_r_groups
from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds
from app.services.smiles_validation import validate_and_standardize_smiles


@dataclass(frozen=True)
class MoleculeModificationResult:
    smiles: str
    core_smiles: str


@dataclass(frozen=True)
class DecomposedStructureRGroup:
    r_label: str
    r_group: str


@dataclass(frozen=True)
class DecomposedStructureResult:
    canonical_smiles: str
    reduced_core: str
    labeled_core_smiles: str
    attachment_points: list[str]
    r_groups: list[DecomposedStructureRGroup]


class MoleculeModificationService:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    @staticmethod
    def _clone_with_source(mol: Chem.Mol, source: str) -> Chem.Mol:
        copied = Chem.Mol(mol)
        for atom in copied.GetAtoms():
            atom.SetProp("_assembly_source", source)
        return copied

    @staticmethod
    def _require_valid_mol(smiles: str, *, label: str) -> Chem.Mol:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid {label} SMILES: {smiles}")
        return mol

    def decompose_structure(
        self,
        *,
        current_smiles: str,
    ) -> DecomposedStructureResult:
        validation = validate_and_standardize_smiles(current_smiles)
        if validation.mol is None or validation.canonical_smiles is None:
            raise ValueError(validation.error or "Current molecule is not a valid structure")

        assignments = analyze_scaffolds([ScaffoldInput(compound_id=1, mol=validation.mol)])
        reduced_core = assignments[1].reduced_core
        if not reduced_core:
            raise ValueError("Unable to extract a reduced core from the current molecule")

        decomposition = decompose_r_groups(
            core_smiles=reduced_core,
            compounds=[RGroupInput(compound_id=1, patent_id=0, mol=validation.mol)],
        )
        labeled_core = decomposition.core_smiles_by_compound.get(1)
        if not labeled_core:
            raise ValueError("Unable to derive labeled attachment placeholders for the current molecule")

        r_groups = sorted(
            [
                DecomposedStructureRGroup(r_label=row.r_label, r_group=row.r_group)
                for row in decomposition.r_groups
                if row.compound_id == 1
            ],
            key=lambda item: item.r_label,
        )
        attachment_points = sorted({item.r_label for item in r_groups})
        self.logger.info(
            "Extracted current labeled core %s with %s attachment groups.",
            labeled_core,
            len(r_groups),
        )
        return DecomposedStructureResult(
            canonical_smiles=validation.canonical_smiles,
            reduced_core=reduced_core,
            labeled_core_smiles=labeled_core,
            attachment_points=attachment_points,
            r_groups=r_groups,
        )

    def _extract_current_series_state(
        self,
        *,
        current_smiles: str,
    ) -> tuple[str, dict[str, str]]:
        decomposition = self.decompose_structure(current_smiles=current_smiles)
        r_group_map = {item.r_label: item.r_group for item in decomposition.r_groups}
        return decomposition.labeled_core_smiles, r_group_map

    def _assemble_from_core_and_rgroups(
        self,
        *,
        labeled_core_smiles: str,
        r_group_map: dict[str, str],
    ) -> str:
        core_mol = self._require_valid_mol(labeled_core_smiles, label="core")
        combined = self._clone_with_source(core_mol, "core")

        for label, r_group_smiles in sorted(r_group_map.items()):
            if not r_group_smiles.strip():
                continue
            fragment = self._require_valid_mol(r_group_smiles, label=f"R-group {label}")
            combined = Chem.CombineMols(combined, self._clone_with_source(fragment, label))

        editable = Chem.RWMol(combined)
        attachments_by_map: dict[int, list[tuple[int, int, Chem.BondType, str]]] = {}
        for atom in editable.GetAtoms():
            if atom.GetAtomicNum() != 0:
                continue
            atom_map_num = atom.GetAtomMapNum()
            if atom_map_num <= 0:
                continue
            neighbors = atom.GetNeighbors()
            if len(neighbors) != 1:
                continue
            neighbor = neighbors[0]
            bond = editable.GetBondBetweenAtoms(atom.GetIdx(), neighbor.GetIdx())
            if bond is None:
                continue
            attachments_by_map.setdefault(atom_map_num, []).append(
                (
                    atom.GetIdx(),
                    neighbor.GetIdx(),
                    bond.GetBondType(),
                    atom.GetProp("_assembly_source") if atom.HasProp("_assembly_source") else "",
                )
            )

        atoms_to_remove: set[int] = set()
        for atom_map_num, attachments in attachments_by_map.items():
            core_entries = [item for item in attachments if item[3] == "core"]
            fragment_entries = [item for item in attachments if item[3] != "core"]
            if not core_entries or not fragment_entries:
                continue

            core_dummy_idx, core_neighbor_idx, core_bond_type, _ = core_entries[0]
            fragment_dummy_idx, fragment_neighbor_idx, fragment_bond_type, _ = fragment_entries[0]
            editable.AddBond(
                core_neighbor_idx,
                fragment_neighbor_idx,
                order=core_bond_type or fragment_bond_type,
            )
            atoms_to_remove.add(core_dummy_idx)
            atoms_to_remove.add(fragment_dummy_idx)
            self.logger.info("Connected attachment point R%s during molecule assembly.", atom_map_num)

        for atom_idx in sorted(atoms_to_remove, reverse=True):
            editable.RemoveAtom(atom_idx)

        assembled_mol = editable.GetMol()
        assembled_smiles = Chem.MolToSmiles(assembled_mol, canonical=True)
        validation = validate_and_standardize_smiles(assembled_smiles)
        if validation.canonical_smiles is None:
            raise ValueError(validation.error or "Failed to validate assembled molecule")
        return validation.canonical_smiles

    def apply_modification(
        self,
        *,
        current_smiles: str,
        target_core_smiles: str | None = None,
        attachment_point: str | None = None,
        rgroup_smiles: str | None = None,
    ) -> MoleculeModificationResult:
        current_labeled_core, current_rgroup_map = self._extract_current_series_state(current_smiles=current_smiles)

        base_core_smiles = (target_core_smiles or current_labeled_core).strip()
        if not base_core_smiles:
            raise ValueError("No target core available for modification")

        if target_core_smiles and "[*:" not in base_core_smiles:
            raise ValueError("Target core does not include attachment placeholders")
        if attachment_point and not attachment_point.strip():
            raise ValueError("attachment_point must not be blank")
        if rgroup_smiles and not attachment_point:
            raise ValueError("attachment_point is required when applying an R-group")

        if attachment_point and rgroup_smiles:
            current_rgroup_map[attachment_point.strip()] = rgroup_smiles.strip()

        self.logger.info(
            "Applying modification with base core %s and %s attachment groups.",
            base_core_smiles,
            len(current_rgroup_map),
        )

        updated_smiles = self._assemble_from_core_and_rgroups(
            labeled_core_smiles=base_core_smiles,
            r_group_map=current_rgroup_map,
        )
        return MoleculeModificationResult(
            smiles=updated_smiles,
            core_smiles=base_core_smiles,
        )
