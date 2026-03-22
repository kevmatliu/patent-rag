from __future__ import annotations

from pydantic import BaseModel


class ResetDatabaseResponse(BaseModel):
    patents_deleted: int
    compounds_deleted: int
    jobs_deleted: int
    logs_deleted: int
    files_deleted: int
