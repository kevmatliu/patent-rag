from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/format", tags=["format"])

class ConvertRequest(BaseModel):
    struct: str

class MolfileResponse(BaseModel):
    molfile: str

class SmilesResponse(BaseModel):
    smiles: str


class SvgResponse(BaseModel):
    svg: str

@router.post("/smiles-to-mol", response_model=MolfileResponse)
def smiles_to_mol(request: ConvertRequest):
    try:
        mol = Chem.MolFromSmiles(request.struct.strip())
        if mol is None:
            raise HTTPException(status_code=400, detail="Invalid SMILES structure.")
        
        # Calculate 2D coordinates so Ketcher draws it properly
        AllChem.Compute2DCoords(mol)
        
        molfile = Chem.MolToMolBlock(mol)
        return MolfileResponse(molfile=molfile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error converting SMILES to Molfile", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mol-to-smiles", response_model=SmilesResponse)
def mol_to_smiles(request: ConvertRequest):
    try:
        mol = Chem.MolFromMolBlock(request.struct.strip())
        if mol is None:
            raise HTTPException(status_code=400, detail="Invalid Molfile structure.")
            
        smiles = Chem.MolToSmiles(mol)
        return SmilesResponse(smiles=smiles)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error converting Molfile to SMILES", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smiles-to-svg", response_model=SvgResponse)
def smiles_to_svg(request: ConvertRequest):
    try:
        mol = Chem.MolFromSmiles(request.struct.strip())
        if mol is None:
            raise HTTPException(status_code=400, detail="Invalid SMILES structure.")

        AllChem.Compute2DCoords(mol)
        drawer = rdMolDraw2D.MolDraw2DSVG(280, 180)
        drawer.drawOptions().padding = 0.08
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        return SvgResponse(svg=drawer.GetDrawingText())
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error converting SMILES to SVG", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
