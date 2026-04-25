from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold

smiles = "CCOc1ccc(CC2=C(C(O)=O)OC(=O)c3ccccc32)cc1"
mol = Chem.MolFromSmiles(smiles)
scaffold = MurckoScaffold.GetScaffoldForMol(mol)

bond_ids = set([5]) # Arbitrary bond from inside 
fragmented = Chem.FragmentOnBonds(scaffold, [5], addDummies=True)

# Replace all Dummies with Hydrogens
dummy = Chem.MolFromSmarts("[*]")
h_atom = Chem.MolFromSmiles("[H]")

for fragment in Chem.GetMolFrags(fragmented, asMols=True, sanitizeFrags=False):
    clean_mol = Chem.ReplaceSubstructs(fragment, dummy, h_atom, replaceAll=True)[0]
    # Remove hydrogens to collapse them implicitly
    clean_mol = Chem.RemoveHs(clean_mol)
    Chem.SanitizeMol(clean_mol)
    print("Clean Fragment:", Chem.MolToSmiles(clean_mol, canonical=True))

