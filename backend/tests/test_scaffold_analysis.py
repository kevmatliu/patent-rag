from __future__ import annotations

from rdkit import Chem

from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds


def test_scaffold_analysis_returns_murcko_assignments_and_counts():
    assignments = analyze_scaffolds(
        [
            ScaffoldInput(compound_id=1, mol=Chem.MolFromSmiles("c1ccccc1Cl")),
            ScaffoldInput(compound_id=2, mol=Chem.MolFromSmiles("c1ccccc1OC")),
            ScaffoldInput(compound_id=3, mol=Chem.MolFromSmiles("c1ccccc1F")),
            ScaffoldInput(compound_id=4, mol=Chem.MolFromSmiles("C1CCCCC1Cl")),
            ScaffoldInput(compound_id=5, mol=Chem.MolFromSmiles("C1CCCCC1Br")),
            ScaffoldInput(compound_id=6, mol=Chem.MolFromSmiles("CCO")),
        ]
    )

    assert assignments[1].murcko_scaffold_smiles == "c1ccccc1"
    assert assignments[1].reduced_core == "c1ccccc1"
    assert assignments[1].scaffold_count == 3
    assert assignments[2].murcko_scaffold_smiles == "c1ccccc1"
    assert assignments[2].reduced_core == "c1ccccc1"
    assert assignments[2].scaffold_count == 3
    assert assignments[3].murcko_scaffold_smiles == "c1ccccc1"
    assert assignments[3].reduced_core == "c1ccccc1"
    assert assignments[3].scaffold_count == 3
    assert assignments[4].murcko_scaffold_smiles == "C1CCCCC1"
    assert assignments[4].reduced_core == "C1CCCCC1"
    assert assignments[4].scaffold_count == 2
    assert assignments[5].murcko_scaffold_smiles == "C1CCCCC1"
    assert assignments[5].reduced_core == "C1CCCCC1"
    assert assignments[5].scaffold_count == 2
    assert assignments[6].murcko_scaffold_smiles is None
    assert assignments[6].reduced_core is None
    assert assignments[6].scaffold_count == 0


def test_scaffold_analysis_handles_empty_input():
    assignments = analyze_scaffolds(
        [
        ]
    )

    assert assignments == {}


def test_scaffold_analysis_picks_best_brics_reduced_core():
    assignments = analyze_scaffolds(
        [
            ScaffoldInput(compound_id=1, mol=Chem.MolFromSmiles("c1ccc(cc1)CCc2ccccc2Cl")),
        ]
    )

    assert assignments[1].murcko_scaffold_smiles == "c1ccc(CCc2ccccc2)cc1"
    assert assignments[1].reduced_core == "c1ccccc1"
    assert assignments[1].scaffold_count == 1
