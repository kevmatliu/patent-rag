from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.dependencies import get_processing_service, get_vector_index_service, get_chemberta_service
from app.db.session import get_session
from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup
from app.models.compound_image import CompoundImage
from app.models.enums import ProcessingStatus
from app.models.patent import Patent
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.repositories.compound_core_candidate_r_group_repository import CompoundCoreCandidateRGroupRepository
from app.repositories.compound_image_repository import CompoundImageRepository
from app.repositories.job_repository import JobRepository
from app.repositories.patent_repository import PatentRepository
from app.schemas.compound_browser import (
    CompoundBrowserItem,
    CompoundBrowserResponse,
    CompoundSpaceNode,
    CompoundSpaceCluster,
    CompoundSpaceResponse,
    CompoundCoreCandidateItem,
    CompoundCoreCandidateRGroupItem,
    CompoundCoreCandidateRGroupResponse,
    CompoundDetailResponse,
    CompoundSelectionRequest,
    CompoundSelectionResponse,
    PatentSelectionRequest,
    SaveCompoundRequest,
    SaveCompoundResponse,
)
from app.schemas.job import JobAcceptedResponse
from app.schemas.image_processing import ProcessFailure
from app.services.chemberta_service import ChemBertaService
from app.services.processing_service import ProcessingService
from app.services.scaffold_analysis import analyze_scaffolds, ScaffoldInput


router = APIRouter(prefix="/api/compounds", tags=["compounds"])

compound_repository = CompoundImageRepository()
core_candidate_repository = CompoundCoreCandidateRepository()
r_group_repository = CompoundCoreCandidateRGroupRepository()
patent_repository = PatentRepository()
job_repository = JobRepository()


def _to_image_url(image_path_value: str, upload_root: Path) -> str:
    image_path = Path(image_path_value).resolve()
    try:
        relative_image = image_path.relative_to(upload_root)
    except ValueError:
        relative_image = Path(image_path.name)
    return f"/static/{relative_image.as_posix()}"


def _build_browser_item(
    compound_row: CompoundImage,
    patent_row,
    *,
    image_url: str,
    candidate_summary: dict[str, int | None] | None = None,
) -> CompoundBrowserItem:
    return CompoundBrowserItem(
        compound_id=compound_row.id or 0,
        patent_id=patent_row.id or 0,
        patent_code=patent_row.patent_slug,
        patent_source_url=patent_row.source_url,
        image_url=image_url,
        page_number=compound_row.page_number,
        processing_status=compound_row.processing_status.value,
        smiles=compound_row.smiles,
        canonical_smiles=compound_row.canonical_smiles,
        is_duplicate_within_patent=compound_row.is_duplicate_within_patent,
        duplicate_of_compound_id=compound_row.duplicate_of_compound_id,
        kept_for_series_analysis=compound_row.kept_for_series_analysis,
        core_candidate_count=int((candidate_summary or {}).get("core_candidate_count") or 0),
        selected_core_candidate_id=(candidate_summary or {}).get("selected_core_candidate_id"),
        validation_error=compound_row.validation_error,
        pipeline_version=compound_row.pipeline_version,
        has_embedding=compound_row.embedding is not None,
        created_at=compound_row.created_at.isoformat(),
        updated_at=compound_row.updated_at.isoformat(),
        last_error=compound_row.last_error,
    )


MAP_PROJECTION_CACHE: dict[str, np.ndarray | None] = {
    "mean": None,
    "components": None,
    "mins": None,
    "spans": None,
}


def _project_embeddings_to_2d(embeddings: list[list[float]]) -> np.ndarray:
    matrix = np.array(embeddings, dtype=np.float32)
    if matrix.shape[0] == 0:
        return np.zeros((0, 2), dtype=np.float32)

    mean_vec = matrix.mean(axis=0, keepdims=True)
    centered = matrix - mean_vec
    if matrix.shape[0] == 1:
        MAP_PROJECTION_CACHE["mean"] = mean_vec
        MAP_PROJECTION_CACHE["components"] = np.zeros((centered.shape[1], 2), dtype=np.float32)
        return np.zeros((1, 2), dtype=np.float32)

    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:2].T if vt.shape[0] >= 2 else vt[:1].T
    
    MAP_PROJECTION_CACHE["mean"] = mean_vec
    MAP_PROJECTION_CACHE["components"] = components
    
    projected = centered @ components
    if projected.shape[1] == 1:
        projected = np.column_stack([projected[:, 0], np.zeros(projected.shape[0], dtype=np.float32)])
    return projected.astype(np.float32)


def _normalize_coordinates(coords: np.ndarray) -> np.ndarray:
    if coords.size == 0:
        return np.zeros((0, 2), dtype=np.float32)

    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    spans = np.where((maxs - mins) == 0, 1.0, (maxs - mins))
    
    MAP_PROJECTION_CACHE["mins"] = mins
    MAP_PROJECTION_CACHE["spans"] = spans
    
    normalized = (coords - mins) / spans
    return normalized.astype(np.float32)


def _determine_cluster_count(point_count: int) -> int:
    if point_count <= 1:
        return 1
    return min(point_count, min(12, max(4, round(math.sqrt(point_count / 2)))))


def _assign_clusters(coords: np.ndarray) -> np.ndarray:
    point_count = coords.shape[0]
    if point_count == 0:
        return np.zeros((0,), dtype=np.int32)
    if point_count == 1:
        return np.zeros((1,), dtype=np.int32)

    cluster_count = _determine_cluster_count(point_count)
    ordered_indices = np.lexsort((coords[:, 1], coords[:, 0]))
    seed_positions = np.linspace(0, point_count - 1, cluster_count, dtype=int)
    centroids = coords[ordered_indices[seed_positions]].copy()
    assignments = np.zeros(point_count, dtype=np.int32)

    for _ in range(32):
        distances = ((coords[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        next_assignments = distances.argmin(axis=1).astype(np.int32)
        if np.array_equal(assignments, next_assignments):
            break
        assignments = next_assignments
        for cluster_index in range(cluster_count):
            members = coords[assignments == cluster_index]
            if members.shape[0] > 0:
                centroids[cluster_index] = members.mean(axis=0)

    centroid_order = np.lexsort((centroids[:, 1], centroids[:, 0]))
    remap = {int(old_index): new_index for new_index, old_index in enumerate(centroid_order.tolist())}
    return np.array([remap[int(cluster_id)] for cluster_id in assignments], dtype=np.int32)


@router.get("", response_model=CompoundBrowserResponse)
def browse_compounds(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    patent_code: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> CompoundBrowserResponse:
    settings = get_settings()
    rows, total = compound_repository.list_browser_rows(
        session,
        offset=offset,
        limit=limit,
        patent_code=patent_code.strip() if patent_code else None,
    )

    items = []
    upload_root = settings.upload_dir.resolve()
    compound_ids = [compound_row.id for compound_row, _ in rows if compound_row.id is not None]
    candidate_summary_by_compound_id = core_candidate_repository.summarize_by_compound_ids(session, compound_ids)
    for compound_row, patent_row in rows:
        items.append(
            _build_browser_item(
                compound_row,
                patent_row,
                image_url=_to_image_url(compound_row.image_path, upload_root),
                candidate_summary=candidate_summary_by_compound_id.get(compound_row.id or 0),
            )
        )

    return CompoundBrowserResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/map", response_model=CompoundSpaceResponse)
def get_compound_space_map(
    session: Session = Depends(get_session),
) -> CompoundSpaceResponse:
    settings = get_settings()
    upload_root = settings.upload_dir.resolve()
    rows = list(
        session.exec(
            select(CompoundImage, Patent)
            .join(Patent, Patent.id == CompoundImage.patent_id)
            .where(CompoundImage.embedding.is_not(None))
            .order_by(CompoundImage.id)
        ).all()
    )

    if not rows:
        return CompoundSpaceResponse(nodes=[], clusters=[])

    embeddings = [json.loads(compound_row.embedding or "[]") for compound_row, _ in rows]
    projected = _normalize_coordinates(_project_embeddings_to_2d(embeddings))
    cluster_ids = _assign_clusters(projected)

    nodes: list[CompoundSpaceNode] = []
    cluster_buckets: dict[int, list[tuple[CompoundImage, Patent, np.ndarray]]] = {}

    for index, (compound_row, patent_row) in enumerate(rows):
        cluster_id = int(cluster_ids[index])
        coords = projected[index]
        node = CompoundSpaceNode(
            compound_id=compound_row.id or 0,
            patent_id=patent_row.id or 0,
            patent_code=patent_row.patent_slug,
            patent_source_url=patent_row.source_url,
            image_url=_to_image_url(compound_row.image_path, upload_root),
            page_number=compound_row.page_number,
            smiles=compound_row.smiles,
            canonical_smiles=compound_row.canonical_smiles,
            has_embedding=compound_row.embedding is not None,
            x=float(coords[0]),
            y=float(coords[1]),
            cluster_id=cluster_id,
        )
        nodes.append(node)
        cluster_buckets.setdefault(cluster_id, []).append((compound_row, patent_row, coords))

    clusters: list[CompoundSpaceCluster] = []
    for cluster_id in sorted(cluster_buckets):
        members = cluster_buckets[cluster_id]
        coords = np.stack([member_coords for _, _, member_coords in members])
        patent_counts: dict[str, int] = {}
        for _, patent_row, _ in members:
            patent_counts[patent_row.patent_slug] = patent_counts.get(patent_row.patent_slug, 0) + 1

        clusters.append(
            CompoundSpaceCluster(
                cluster_id=cluster_id,
                x=float(coords[:, 0].mean()),
                y=float(coords[:, 1].mean()),
                member_count=len(members),
                patent_counts=dict(sorted(patent_counts.items(), key=lambda item: (-item[1], item[0]))),
            )
        )

    return CompoundSpaceResponse(nodes=nodes, clusters=clusters)


@router.get("/core-candidates/{core_candidate_id}/r-groups", response_model=CompoundCoreCandidateRGroupResponse)
def get_core_candidate_r_groups(
    core_candidate_id: int,
    session: Session = Depends(get_session),
) -> CompoundCoreCandidateRGroupResponse:
    core_candidate = core_candidate_repository.get_by_id(session, core_candidate_id)
    if core_candidate is None:
        raise HTTPException(status_code=404, detail="Core candidate not found")

    rows = r_group_repository.list_by_core_candidate_id(session, core_candidate_id)
    return CompoundCoreCandidateRGroupResponse(
        compound_id=core_candidate.compound_id,
        core_candidate_id=core_candidate_id,
        items=[
            CompoundCoreCandidateRGroupItem(
                core_candidate_id=row.core_candidate_id,
                compound_id=row.compound_id,
                patent_id=row.patent_id,
                r_label=row.r_label,
                r_group_smiles=row.r_group_smiles,
                attachment_index=row.attachment_index,
                pipeline_version=row.pipeline_version,
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ],
    )


@router.get("/{compound_id}/r-groups", response_model=CompoundCoreCandidateRGroupResponse)
def get_compound_r_groups_deprecated(
    compound_id: int,
    session: Session = Depends(get_session),
) -> CompoundCoreCandidateRGroupResponse:
    candidates = core_candidate_repository.list_by_compound_id(session, compound_id)
    if not candidates:
        raise HTTPException(status_code=404, detail="No core candidates found for compound")
    selected = candidates[0]
    return get_core_candidate_r_groups(selected.id or 0, session)


@router.get("/{compound_id}", response_model=CompoundDetailResponse)
def get_compound_detail(
    compound_id: int,
    session: Session = Depends(get_session),
) -> CompoundDetailResponse:
    compound = session.get(CompoundImage, compound_id)
    if compound is None:
        raise HTTPException(status_code=404, detail="Compound not found")

    patent = session.get(Patent, compound.patent_id)
    if patent is None:
        raise HTTPException(status_code=404, detail="Patent not found")

    settings = get_settings()
    candidate_summary = core_candidate_repository.summarize_by_compound_ids(session, [compound_id]).get(compound_id)
    candidates = core_candidate_repository.list_by_compound_id(session, compound_id)

    return CompoundDetailResponse(
        compound=_build_browser_item(
            compound,
            patent,
            image_url=_to_image_url(compound.image_path, settings.upload_dir.resolve()),
            candidate_summary=candidate_summary,
        ),
        core_candidates=[
            CompoundCoreCandidateItem(
                id=row.id or 0,
                compound_id=row.compound_id,
                patent_id=row.patent_id,
                candidate_rank=row.candidate_rank,
                is_selected=row.is_selected,
                core_smiles=row.core_smiles,
                core_smarts=row.core_smarts,
                reduced_core=row.reduced_core,
                murcko_scaffold_smiles=row.murcko_scaffold_smiles,
                generation_method=row.generation_method,
                pipeline_version=row.pipeline_version,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat(),
            )
            for row in candidates
        ],
    )


def _rebuild_index(session: Session) -> None:
    vector_index = get_vector_index_service()
    items = []
    for image in compound_repository.list_indexable(session):
        if image.id is None or image.embedding is None:
            continue
        items.append((image.id, json.loads(image.embedding)))
    vector_index.rebuild(items)


def _run_selected_processing_job(
    job_id: str,
    limit: int,
    processing_service: ProcessingService,
) -> None:
    from app.db.session import engine

    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            return

        job_repository.start_job(session, job)
        def log_progress(level: str, message: str) -> None:
            job_repository.add_log(session, job_id=job_id, level=level, message=message)

        summary_raw = json.loads(job.summary) if job.summary else {}
        result = processing_service.process_images(
            session,
            limit=limit,
            order="oldest",
            compound_ids=summary_raw.get("compound_ids") or [],
            progress_callback=log_progress,
            should_stop=lambda: job_repository.is_cancel_requested(session, job_id),
        )
        summary = {
            "processed_count": len(result.processed_image_ids),
            "failed_count": len(result.failures),
            "processed_image_ids": result.processed_image_ids,
            "failures": [
                ProcessFailure(image_id=item.image_id, error=item.error).model_dump()
                for item in result.failures
            ],
            "stopped_early": result.stopped_early,
        }
        if result.stopped_early:
            job_repository.cancel_job(session, job, summary=summary)
        else:
            job_repository.complete_job(session, job, summary=summary)


@router.post("/delete", response_model=CompoundSelectionResponse)
def delete_compounds(
    payload: CompoundSelectionRequest,
    session: Session = Depends(get_session),
) -> CompoundSelectionResponse:
    deleted = compound_repository.delete_by_ids(session, compound_ids=payload.compound_ids)
    _rebuild_index(session)
    return CompoundSelectionResponse(affected_count=deleted)


@router.post("/reprocess", response_model=JobAcceptedResponse)
def reprocess_compounds(
    payload: CompoundSelectionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    processing_service: ProcessingService = Depends(get_processing_service),
) -> JobAcceptedResponse:
    reset_count = compound_repository.reset_for_reprocess(session, compound_ids=payload.compound_ids)
    _rebuild_index(session)
    job = job_repository.create_job(session, job_type="image_processing")
    job.summary = json.dumps({"compound_ids": payload.compound_ids})
    session.add(job)
    session.commit()
    session.refresh(job)
    job_repository.add_log(session, job_id=job.id, message=f"Queued {reset_count} compound(s) for reprocessing.")
    background_tasks.add_task(_run_selected_processing_job, job.id, reset_count, processing_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.post("/reprocess-patents", response_model=JobAcceptedResponse)
def reprocess_patents(
    payload: PatentSelectionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    processing_service: ProcessingService = Depends(get_processing_service),
) -> JobAcceptedResponse:
    patent_ids = [patent_id for patent_id in payload.patent_ids if patent_id > 0]
    compound_ids = [
        compound_id
        for compound_id in session.exec(select(CompoundImage.id).where(CompoundImage.patent_id.in_(patent_ids))).all()
        if compound_id is not None
    ]
    if not compound_ids:
        raise HTTPException(status_code=404, detail="No compounds found for the selected patents")

    reset_count = compound_repository.reset_for_reprocess(session, compound_ids=compound_ids)
    _rebuild_index(session)
    job = job_repository.create_job(session, job_type="image_processing")
    job.summary = json.dumps({"compound_ids": compound_ids})
    session.add(job)
    session.commit()
    session.refresh(job)
    job_repository.add_log(
        session,
        job_id=job.id,
        message=f"Queued {reset_count} compound(s) across {len(patent_ids)} patent(s) for reprocessing.",
    )
    background_tasks.add_task(_run_selected_processing_job, job.id, reset_count, processing_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.delete("/patent/{patent_code}", response_model=CompoundSelectionResponse)
def delete_patent(
    patent_code: str,
    session: Session = Depends(get_session),
) -> CompoundSelectionResponse:
    patent = patent_repository.get_by_slug(session, patent_code)
    if patent is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    compound_ids = [item.id for item in session.exec(select(CompoundImage).where(CompoundImage.patent_id == patent.id)).all() if item.id]
    deleted = compound_repository.delete_by_ids(session, compound_ids=compound_ids)
    patent_repository.delete(session, patent)
    _rebuild_index(session)
    return CompoundSelectionResponse(affected_count=deleted)


@router.post("/save", response_model=SaveCompoundResponse)
def save_compound(
    payload: SaveCompoundRequest,
    session: Session = Depends(get_session),
    chemberta_service: ChemBertaService = Depends(get_chemberta_service),
) -> SaveCompoundResponse:
    settings = get_settings()

    mol = Chem.MolFromSmiles(payload.smiles)
    if not mol:
        raise HTTPException(status_code=400, detail="Invalid SMILES")

    canonical_smiles = Chem.MolToSmiles(mol)

    existing = session.exec(select(CompoundImage).where(CompoundImage.canonical_smiles == canonical_smiles)).first()
    if existing and existing.id:
        return SaveCompoundResponse(compound_id=existing.id)

    patent = patent_repository.get_by_slug(session, "user-structures")
    if not patent:
        patent = patent_repository.create(
            session,
            patent_slug="user-structures",
            source_url="user://structures",
        )

    save_dir = settings.upload_dir / "user_structures"
    save_dir.mkdir(parents=True, exist_ok=True)
    image_filename = f"{uuid.uuid4().hex}.svg"
    image_path = save_dir / image_filename

    drawer = rdMolDraw2D.MolDraw2DSVG(300, 300)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    image_path.write_text(drawer.GetDrawingText())

    embedding = chemberta_service.smiles_to_embedding(canonical_smiles)

    compound = CompoundImage(
        patent_id=patent.id,
        image_path=str(image_path),
        processing_status=ProcessingStatus.PROCESSED,
        smiles=payload.smiles,
        canonical_smiles=canonical_smiles,
        embedding=json.dumps(embedding),
        is_compound=True,
    )
    session.add(compound)
    session.flush()
    compound_id = compound.id
    
    assert compound_id is not None

    scaffold_res_map = analyze_scaffolds([ScaffoldInput(compound_id=compound_id, mol=mol)])
    scaffold_res = scaffold_res_map.get(compound_id)
    
    if scaffold_res:
        core_cand = CompoundCoreCandidate(
            compound_id=compound_id,
            patent_id=patent.id,
            core_smiles=scaffold_res.murcko_scaffold_smiles,
            reduced_core=scaffold_res.reduced_core,
            is_selected=True,
            pipeline_version="direct-save"
        )
        session.add(core_cand)
        session.flush()

    session.commit()

    vector_index = get_vector_index_service()
    vector_index.add_vector(compound_id, embedding)

    return SaveCompoundResponse(compound_id=compound_id)
