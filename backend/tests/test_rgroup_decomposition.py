from __future__ import annotations

from rdkit import Chem

from app.services.rgroup_decomposition import RGroupInput, decompose_r_groups


def test_rgroup_decomposition_returns_labeled_rows():
    result = decompose_r_groups(
        core_smiles="c1ccccc1",
        compounds=[
            RGroupInput(compound_id=1, patent_id=10, mol=Chem.MolFromSmiles("c1ccccc1Cl")),
            RGroupInput(compound_id=2, patent_id=10, mol=Chem.MolFromSmiles("c1ccccc1OC")),
        ],
    )

    assert result.unmatched_compound_ids == []
    assert set(result.core_smiles_by_compound) == {1, 2}
    assert set(result.core_smarts_by_compound) == {1, 2}
    assert {row.compound_id for row in result.r_groups} == {1, 2}
    assert {row.r_label for row in result.r_groups} == {"R1"}
    assert all(row.core_smiles for row in result.r_groups)
    assert all(row.r_group for row in result.r_groups)
