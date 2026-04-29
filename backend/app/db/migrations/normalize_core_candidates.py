from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text


def _table_exists(connection, table_name: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name = :table_name"),
        {"table_name": table_name},
    ).fetchone()
    return row is not None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(column[1] == column_name for column in columns)


def _attachment_index_from_label(label: str | None) -> int | None:
    if not label or not label.startswith("R"):
        return None
    suffix = label[1:]
    return int(suffix) if suffix.isdigit() else None


def upgrade(connection) -> None:
    if not _table_exists(connection, "compound_core_candidate"):
        return

    if _column_exists(connection, "compoundimage", "murcko_scaffold_smiles"):
        connection.execute(
            text(
                """
                INSERT INTO compound_core_candidate (
                    compound_id,
                    patent_id,
                    candidate_rank,
                    is_selected,
                    core_smiles,
                    core_smarts,
                    reduced_core,
                    murcko_scaffold_smiles,
                    generation_method,
                    pipeline_version,
                    created_at,
                    updated_at
                )
                SELECT
                    ci.id,
                    ci.patent_id,
                    1,
                    1,
                    ci.core_smiles,
                    ci.core_smarts,
                    ci.reduced_core,
                    ci.murcko_scaffold_smiles,
                    'legacy_compound_image_migration',
                    ci.pipeline_version,
                    ci.created_at,
                    ci.updated_at
                FROM compoundimage ci
                WHERE (
                    ci.murcko_scaffold_smiles IS NOT NULL
                    OR ci.reduced_core IS NOT NULL
                    OR ci.core_smiles IS NOT NULL
                    OR ci.core_smarts IS NOT NULL
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM compound_core_candidate ccc
                    WHERE ccc.compound_id = ci.id
                )
                """
            )
        )

    if not _table_exists(connection, "compound_r_group") or not _table_exists(connection, "compound_core_candidate_r_group"):
        return

    candidate_rows = connection.execute(
        text(
            """
            SELECT id, compound_id
            FROM compound_core_candidate
            ORDER BY compound_id, is_selected DESC, candidate_rank ASC, id ASC
            """
        )
    ).mappings()
    candidate_id_by_compound_id: dict[int, int] = {}
    for row in candidate_rows:
        candidate_id_by_compound_id.setdefault(int(row["compound_id"]), int(row["id"]))

    existing_rows = connection.execute(
        text(
            """
            SELECT core_candidate_id, r_label, r_group_smiles, COALESCE(attachment_index, -1) AS attachment_index
            FROM compound_core_candidate_r_group
            """
        )
    ).mappings()
    existing_keys = {
        (
            int(row["core_candidate_id"]),
            str(row["r_label"]),
            str(row["r_group_smiles"]),
            int(row["attachment_index"]),
        )
        for row in existing_rows
    }

    legacy_rows = connection.execute(
        text(
            """
            SELECT compound_id, patent_id, r_label, r_group, pipeline_version, created_at
            FROM compound_r_group
            ORDER BY compound_id, id
            """
        )
    ).mappings()

    now = datetime.now(timezone.utc)
    for row in legacy_rows:
        compound_id = int(row["compound_id"])
        core_candidate_id = candidate_id_by_compound_id.get(compound_id)
        if core_candidate_id is None:
            continue
        attachment_index = _attachment_index_from_label(row["r_label"])
        dedupe_key = (
            core_candidate_id,
            str(row["r_label"]),
            str(row["r_group"]),
            attachment_index if attachment_index is not None else -1,
        )
        if dedupe_key in existing_keys:
            continue
        connection.execute(
            text(
                """
                INSERT INTO compound_core_candidate_r_group (
                    core_candidate_id,
                    compound_id,
                    patent_id,
                    r_label,
                    r_group_smiles,
                    attachment_index,
                    pipeline_version,
                    created_at
                ) VALUES (
                    :core_candidate_id,
                    :compound_id,
                    :patent_id,
                    :r_label,
                    :r_group_smiles,
                    :attachment_index,
                    :pipeline_version,
                    :created_at
                )
                """
            ),
            {
                "core_candidate_id": core_candidate_id,
                "compound_id": compound_id,
                "patent_id": int(row["patent_id"]),
                "r_label": str(row["r_label"]),
                "r_group_smiles": str(row["r_group"]),
                "attachment_index": attachment_index,
                "pipeline_version": row["pipeline_version"],
                "created_at": row["created_at"] or now,
            },
        )
        existing_keys.add(dedupe_key)


def downgrade(connection) -> None:
    if not _table_exists(connection, "compound_r_group"):
        return
    if not _table_exists(connection, "compound_core_candidate"):
        return

    connection.execute(text("DELETE FROM compound_r_group"))
    connection.execute(
        text(
            """
            INSERT INTO compound_r_group (
                compound_id,
                patent_id,
                core_smiles,
                core_smarts,
                r_label,
                r_group,
                pipeline_version,
                created_at
            )
            SELECT
                ccc.compound_id,
                cccrg.patent_id,
                ccc.core_smiles,
                ccc.core_smarts,
                cccrg.r_label,
                cccrg.r_group_smiles,
                cccrg.pipeline_version,
                cccrg.created_at
            FROM compound_core_candidate_r_group cccrg
            JOIN compound_core_candidate ccc ON ccc.id = cccrg.core_candidate_id
            """
        )
    )
