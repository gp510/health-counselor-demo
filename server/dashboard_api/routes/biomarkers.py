"""Biomarker API routes."""
from fastapi import APIRouter, Query
from typing import Optional

from ..models.biomarker import Biomarker
from ..database import db_manager

router = APIRouter(prefix="/api/health", tags=["Biomarkers"])


def _row_to_biomarker(row) -> Biomarker:
    """Convert SQLite row to Biomarker model."""
    return Biomarker(
        test_id=row["test_id"],
        test_date=row["test_date"],
        test_type=row["test_type"],
        biomarker_name=row["biomarker_name"],
        value=float(row["value"]),
        unit=row["unit"],
        reference_range_low=float(row["reference_range_low"]),
        reference_range_high=float(row["reference_range_high"]),
        status=row["status"],
        lab_source=row["lab_source"],
        notes=row["notes"],
    )


@router.get("/biomarkers", response_model=list[Biomarker])
async def get_biomarkers(
    limit: int = Query(default=50, ge=1, le=200),
    test_type: Optional[str] = Query(default=None, description="Filter by test type"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """
    Get recent biomarker test results.
    Optionally filter by test type or status.
    """
    with db_manager.get_biomarker_conn() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM biomarker_data WHERE 1=1"
        params = []

        if test_type:
            query += " AND test_type = ?"
            params.append(test_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY test_date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [_row_to_biomarker(row) for row in rows]
