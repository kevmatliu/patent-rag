from rdkit import Chem
from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds

def test_mol(smiles, label):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        print(f"{label}: Failed to parse SMILES")
        return
    results = analyze_scaffolds([ScaffoldInput(compound_id=1, mol=mol)])
    res = results[1]
    print(f"{label}:")
    print(f"  Murcko: {res.murcko_scaffold_smiles}")
    print(f"  Reduced: {res.reduced_core}")

print("Testing core extraction...")
test_mol("Cc1ccc(cc1)C(=O)NCC2=CC=C(C=C2)C(=O)O", "Simple amide")
test_mol("CN1C=C(C=N1)C2=CC=C(C=C2)NC(=O)C3=CC=C(C=C3)CN4CCN(CC4)C", "Crizotinib-like")
test_mol("CCOc1ccc(CC2=C(C(O)=O)OC(=O)c3ccccc32)cc1", "User example")
