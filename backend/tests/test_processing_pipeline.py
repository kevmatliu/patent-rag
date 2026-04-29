from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup
from app.models.compound_image import CompoundImage
from app.models.enums import ProcessingStatus, ValidationStatus
from app.models.patent import Patent
from app.services.processing_service import ProcessingService


class MappingMolScribeService:
    name = "molscribe"
    device = "cpu"

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def image_to_smiles(self, image_path: str) -> str:
        return self.mapping[Path(image_path).name]


class TrackingChemBertaService:
    device = "cpu"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def smiles_to_embedding(self, smiles: str) -> list[float]:
        self.calls.append(smiles)
        return [float(len(smiles)), 0.5, 1.5]


class RecordingVectorIndexService:
    def __init__(self) -> None:
        self.rebuilt_items: list[tuple[int, list[float]]] = []

    def rebuild(self, items: list[tuple[int, list[float]]]) -> None:
        self.rebuilt_items = list(items)


def test_processing_service_runs_full_rdkit_enrichment_pipeline(session_factory, configured_settings, tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    smiles_by_filename = {
        "benzene-cl.png": "c1ccccc1Cl",
        "benzene-cl-dup.png": "Clc1ccccc1",
        "benzene-oc.png": "c1ccccc1OC",
        "benzene-f.png": "c1ccccc1F",
        "cyclohexyl-cl.png": "C1CCCCC1Cl",
        "cyclohexyl-br.png": "C1CCCCC1Br",
        "diphenyl-cl.png": "c1ccc(cc1)CCc1ccccc1Cl",
        "diphenyl-f.png": "c1ccc(cc1)CCc1ccccc1F",
        "ethanol.png": "CCO",
        "invalid.png": "not-a-smiles",
    }
    for filename in smiles_by_filename:
        (image_dir / filename).write_bytes(b"fake-image")

    molscribe = MappingMolScribeService(smiles_by_filename)
    chemberta = TrackingChemBertaService()
    vector_index = RecordingVectorIndexService()
    service = ProcessingService(
        settings=configured_settings,
        smiles_recognition_service=molscribe,
        chemberta_service=chemberta,
        vector_index_service=vector_index,
    )

    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        for filename in smiles_by_filename:
            session.add(CompoundImage(patent_id=patent.id, image_path=str(image_dir / filename)))
        session.commit()

        result = service.process_images(session, limit=20, order="oldest")
        assert len(result.processed_image_ids) == 10
        assert result.failures == []

    with Session(session_factory) as session:
        compounds = list(session.exec(select(CompoundImage).order_by(CompoundImage.id)).all())
        compound_by_name = {Path(item.image_path).name: item for item in compounds}
        core_candidates = list(
            session.exec(
                select(CompoundCoreCandidate).order_by(CompoundCoreCandidate.compound_id, CompoundCoreCandidate.id)
            ).all()
        )
        r_groups = list(
            session.exec(
                select(CompoundCoreCandidateRGroup).order_by(
                    CompoundCoreCandidateRGroup.compound_id,
                    CompoundCoreCandidateRGroup.attachment_index,
                    CompoundCoreCandidateRGroup.r_label,
                )
            ).all()
        )
        candidate_by_compound_id = {item.compound_id: item for item in core_candidates}

    benzene_names = {"benzene-cl.png", "benzene-oc.png", "benzene-f.png"}
    cyclohexyl_names = {"cyclohexyl-cl.png", "cyclohexyl-br.png"}
    reduced_benzene_names = {"diphenyl-cl.png", "diphenyl-f.png"}
    other_name = "ethanol.png"
    duplicate_name = "benzene-cl-dup.png"
    invalid_name = "invalid.png"

    first_image = compound_by_name["benzene-cl.png"]
    duplicate_image = compound_by_name[duplicate_name]
    invalid_image = compound_by_name[invalid_name]

    assert first_image.processing_status == ProcessingStatus.PROCESSED
    assert first_image.validation_status == ValidationStatus.VALID
    assert first_image.canonical_smiles == "Clc1ccccc1"
    assert first_image.is_duplicate_within_patent is False
    assert first_image.kept_for_series_analysis is True
    assert candidate_by_compound_id[first_image.id].core_smarts is not None

    assert duplicate_image.validation_status == ValidationStatus.VALID
    assert duplicate_image.canonical_smiles == first_image.canonical_smiles
    assert duplicate_image.is_duplicate_within_patent is True
    assert duplicate_image.duplicate_of_compound_id == first_image.id
    assert duplicate_image.kept_for_series_analysis is False
    assert duplicate_image.embedding is None

    assert invalid_image.processing_status == ProcessingStatus.PROCESSED
    assert invalid_image.is_compound is False
    assert invalid_image.validation_status == ValidationStatus.PARSE_FAILED
    assert invalid_image.embedding is None
    assert invalid_image.kept_for_series_analysis is False

    for name in benzene_names:
        item = compound_by_name[name]
        candidate = candidate_by_compound_id[item.id]
        assert candidate.murcko_scaffold_smiles == "c1ccccc1"
        assert candidate.reduced_core == "c1ccccc1"
        assert candidate.core_smiles is not None
        assert candidate.core_smarts is not None
        assert item.embedding is not None

    for name in cyclohexyl_names:
        item = compound_by_name[name]
        candidate = candidate_by_compound_id[item.id]
        assert candidate.murcko_scaffold_smiles == "C1CCCCC1"
        assert candidate.reduced_core == "C1CCCCC1"
        assert candidate.core_smiles is not None
        assert candidate.core_smarts is not None
        assert item.embedding is not None

    for name in reduced_benzene_names:
        item = compound_by_name[name]
        candidate = candidate_by_compound_id[item.id]
        assert candidate.murcko_scaffold_smiles == "c1ccc(CCc2ccccc2)cc1"
        assert candidate.reduced_core == "c1ccccc1"
        assert candidate.core_smiles is not None
        assert candidate.core_smarts is not None
        assert item.embedding is not None

    other_item = compound_by_name[other_name]
    assert other_item.id not in candidate_by_compound_id
    assert other_item.embedding is not None

    benzene_ids = {compound_by_name[name].id for name in benzene_names}
    cyclohexyl_ids = {compound_by_name[name].id for name in cyclohexyl_names}
    reduced_benzene_ids = {compound_by_name[name].id for name in reduced_benzene_names}
    assert {row.compound_id for row in r_groups} == benzene_ids | cyclohexyl_ids | reduced_benzene_ids
    assert {row.r_label for row in r_groups} == {"R1"}
    assert all(row.core_candidate_id for row in r_groups)
    assert all(row.r_group_smiles for row in r_groups)

    assert set(chemberta.calls) == {
        "Clc1ccccc1",
        "COc1ccccc1",
        "Fc1ccccc1",
        "ClC1CCCCC1",
        "BrC1CCCCC1",
        "Clc1ccccc1CCc1ccccc1",
        "Fc1ccccc1CCc1ccccc1",
        "CCO",
    }
    assert len(vector_index.rebuilt_items) == 8
    assert {item_id for item_id, _ in vector_index.rebuilt_items} == {
        compound_by_name["benzene-cl.png"].id,
        compound_by_name["benzene-oc.png"].id,
        compound_by_name["benzene-f.png"].id,
        compound_by_name["cyclohexyl-cl.png"].id,
        compound_by_name["cyclohexyl-br.png"].id,
        compound_by_name["diphenyl-cl.png"].id,
        compound_by_name["diphenyl-f.png"].id,
        compound_by_name["ethanol.png"].id,
    }
    assert all(json.loads(compound_by_name[name].embedding) for name in benzene_names | cyclohexyl_names | reduced_benzene_names | {other_name})
