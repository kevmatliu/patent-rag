# Compound Core Normalization

## New hierarchy

Decomposition data is now normalized into three layers:

1. `CompoundImage`
2. `CompoundCoreCandidate`
3. `CompoundCoreCandidateRGroup`

`CompoundImage` remains the parent extracted compound record and stores image provenance, patent/page linkage, canonicalized SMILES, validation state, duplicate flags, embeddings, pipeline metadata, and timestamps.

Candidate decomposition data now lives on `CompoundCoreCandidate`, and R-group fragments now live on `CompoundCoreCandidateRGroup`.

## Why this refactor was done

The previous flat schema attached decomposition fields directly to `CompoundImage` and attached R-groups directly to the compound. That made it hard to support:

- multiple candidate decompositions per compound
- ranking and selection of candidate cores
- inspection of R-groups for one specific decomposition choice

The normalized schema matches the UI flow directly:

- browse compounds
- inspect candidate cores for one compound
- inspect R-groups for one selected core candidate

## Migration behavior

Startup migration logic in [normalize_core_candidates.py](/Users/kevinliu/Desktop/patent-rag-chem/v2/backend/app/db/migrations/normalize_core_candidates.py) performs the forward data migration.

It:

- creates `compound_core_candidate` and `compound_core_candidate_r_group` via the current SQLModel metadata
- migrates legacy decomposition fields from `compoundimage` into one default candidate row per compound when legacy core data exists
- sets `candidate_rank = 1` and `is_selected = true` for migrated default candidates
- maps legacy `compound_r_group` rows onto the migrated default candidate for the same compound
- skips compounds that do not have legacy decomposition data
- preserves the legacy `compoundimage` fields and legacy `compound_r_group` table for transitional compatibility

## Transitional compatibility

The following `CompoundImage` fields are still present temporarily for compatibility with older data:

- `murcko_scaffold_smiles`
- `reduced_core`
- `core_smiles`
- `core_smarts`

New processing writes candidate decomposition data only to the normalized tables and clears those legacy fields during reprocessing so old flat data does not continue to drift out of sync.
