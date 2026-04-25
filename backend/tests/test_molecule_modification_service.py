from __future__ import annotations

from app.services.molecule_modification_service import MoleculeModificationService


def test_decompose_structure_extracts_labeled_core_and_rgroups():
    service = MoleculeModificationService()

    result = service.decompose_structure(current_smiles="Clc1ccccc1")

    assert result.canonical_smiles == "Clc1ccccc1"
    assert result.reduced_core == "c1ccccc1"
    assert result.labeled_core_smiles == "c1ccc([*:1])cc1"
    assert result.attachment_points == ["R1"]
    assert len(result.r_groups) == 1
    assert result.r_groups[0].r_label == "R1"
    assert result.r_groups[0].r_group == "Cl[*:1]"


def test_apply_modification_replaces_rgroup_for_single_attachment_series():
    service = MoleculeModificationService()

    result = service.apply_modification(
        current_smiles="Clc1ccccc1",
        attachment_point="R1",
        rgroup_smiles="F[*:1]",
    )

    assert result.smiles == "Fc1ccccc1"
    assert result.core_smiles == "c1ccc([*:1])cc1"


def test_apply_modification_replaces_core_and_preserves_existing_substituent():
    service = MoleculeModificationService()

    result = service.apply_modification(
        current_smiles="Clc1ccccc1",
        target_core_smiles="C1CCC([*:1])CC1",
    )

    assert result.smiles == "ClC1CCCCC1"
    assert result.core_smiles == "C1CCC([*:1])CC1"
