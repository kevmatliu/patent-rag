from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.dependencies import (
    get_core_recommendation_service,
    get_molecule_modification_service,
    get_rgroup_recommendation_service,
)
from app.db.session import get_session
from app.schemas.recommend import (
    ApplyModificationRequest,
    ApplyModificationResponse,
    DecomposeStructureRequest,
    DecomposeStructureResponse,
    DecomposedStructureRGroupItem,
    ExactCoreRGroupRecommendationColumn,
    ExactCoreRGroupRecommendationRequest,
    ExactCoreRGroupRecommendationResponse,
    RGroupRecommendationItem,
    RGroupRecommendationRequest,
    SimilarCoreRecommendationItem,
    SimilarCoreRecommendationRequest,
)
from app.services.core_recommendation_service import CoreRecommendationService
from app.services.molecule_modification_service import MoleculeModificationService
from app.services.rgroup_recommendation_service import RGroupRecommendationService


router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("/similar-cores", response_model=list[SimilarCoreRecommendationItem])
def recommend_similar_cores(
    payload: SimilarCoreRecommendationRequest,
    session: Session = Depends(get_session),
    recommendation_service: CoreRecommendationService = Depends(get_core_recommendation_service),
) -> list[SimilarCoreRecommendationItem]:
    results = recommendation_service.get_similar_cores(
        session,
        core_smiles=payload.core_smiles,
        k=payload.k,
    )
    return [
        SimilarCoreRecommendationItem(
            core_smiles=item.core_smiles,
            apply_core_smiles=item.apply_core_smiles,
            score=item.score,
            support_count=item.support_count,
            reason=item.reason,
            compound_ids=item.compound_ids or [],
            exact_match=item.exact_match,
        )
        for item in results
    ]


@router.post("/exact-core-rgroups", response_model=ExactCoreRGroupRecommendationResponse)
def recommend_exact_core_rgroups(
    payload: ExactCoreRGroupRecommendationRequest,
    session: Session = Depends(get_session),
    recommendation_service: RGroupRecommendationService = Depends(get_rgroup_recommendation_service),
) -> ExactCoreRGroupRecommendationResponse:
    result = recommendation_service.get_exact_core_rgroup_recommendations(
        session,
        query_smiles=payload.query_smiles,
        attachment_points=payload.attachment_points,
        k=payload.k,
    )
    return ExactCoreRGroupRecommendationResponse(
        query_core_smiles=result.query_core_smiles,
        attachment_points=result.attachment_points,
        exact_core_found=result.exact_core_found,
        columns=[
            ExactCoreRGroupRecommendationColumn(
                attachment_point=column.attachment_point,
                items=[
                    RGroupRecommendationItem(
                        rgroup_smiles=item.rgroup_smiles,
                        count=item.count,
                        reason=item.reason,
                        compound_ids=item.compound_ids,
                        exact_match=item.exact_match,
                    )
                    for item in column.items
                ],
            )
            for column in result.columns
        ],
    )


@router.post("/rgroups", response_model=list[RGroupRecommendationItem])
def recommend_rgroups(
    payload: RGroupRecommendationRequest,
    session: Session = Depends(get_session),
    recommendation_service: RGroupRecommendationService = Depends(get_rgroup_recommendation_service),
) -> list[RGroupRecommendationItem]:
    results = recommendation_service.get_rgroup_suggestions(
        session,
        core_smiles=payload.core_smiles,
        attachment_point=payload.attachment_point,
        k=payload.k,
    )
    return [
        RGroupRecommendationItem(
            rgroup_smiles=item.rgroup_smiles,
            count=item.count,
            reason=item.reason,
            compound_ids=item.compound_ids,
            exact_match=item.exact_match,
        )
        for item in results
    ]


@router.post("/apply-modification", response_model=ApplyModificationResponse)
def apply_modification(
    payload: ApplyModificationRequest,
    modification_service: MoleculeModificationService = Depends(get_molecule_modification_service),
) -> ApplyModificationResponse:
    try:
        result = modification_service.apply_modification(
            current_smiles=payload.current_smiles,
            target_core_smiles=payload.target_core_smiles,
            attachment_point=payload.attachment_point,
            rgroup_smiles=payload.rgroup_smiles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApplyModificationResponse(
        smiles=result.smiles,
        core_smiles=result.core_smiles,
    )


@router.post("/decompose-structure", response_model=DecomposeStructureResponse)
def decompose_structure(
    payload: DecomposeStructureRequest,
    modification_service: MoleculeModificationService = Depends(get_molecule_modification_service),
) -> DecomposeStructureResponse:
    try:
        result = modification_service.decompose_structure(current_smiles=payload.current_smiles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DecomposeStructureResponse(
        canonical_smiles=result.canonical_smiles,
        reduced_core=result.reduced_core,
        labeled_core_smiles=result.labeled_core_smiles,
        attachment_points=result.attachment_points,
        r_groups=[
            DecomposedStructureRGroupItem(r_label=item.r_label, r_group=item.r_group)
            for item in result.r_groups
        ],
    )
