from rdkit import Chem
from rdkit.Chem import BRICS
from rdkit.Chem.Scaffolds import MurckoScaffold

smiles = "CCOc1ccc(CC2=C(C(O)=O)OC(=O)c3ccccc32)cc1"
mol = Chem.MolFromSmiles(smiles)
scaffold = MurckoScaffold.GetScaffoldForMol(mol)
print("Scaffold:", Chem.MolToSmiles(scaffold))

bond_ids = set()
for atom_pair, _ in BRICS.FindBRICSBonds(scaffold):
    bond = scaffold.GetBondBetweenAtoms(*atom_pair)
    if bond is not None:
        bond_ids.add(bond.GetIdx())

for bond_id in bond_ids:
    fragmented = Chem.FragmentOnBonds(scaffold, [bond_id], addDummies=False)
    for fragment in Chem.GetMolFrags(fragmented, asMols=True, sanitizeFrags=False):
        try:
            print("Raw Fragment:", Chem.MolToSmiles(fragment))
            # Neutralize
            for atom in fragment.GetAtoms():
                if atom.GetNumRadicalElectrons() > 0:
                    atom.SetNumRadicalElectrons(0)
                    atom.SetNumExplicitHs(atom.GetNumExplicitHs() + 1)
            Chem.SanitizeMol(fragment)
            print("Neutralized:", Chem.MolToSmiles(fragment, canonical=True))
        except Exception as e:
            print("Error neutralizing:", e)
