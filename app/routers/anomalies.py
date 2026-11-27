from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import AnomalyResponse
from app.ml_engine import ml_engine

router = APIRouter(prefix="/api/anomalies", tags=["Anomaly Detection"])


@router.get("", response_model=List[AnomalyResponse])
def get_anomalies(
    status: Optional[str] = Query(None, description="Filter by status: UNRESOLVED, ACKNOWLEDGED, DISMISSED, or ALL"),
):
    """Retrieve detected consumption anomalies and waste risks."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = """
            SELECT a.*, i.name as item_name, i.category as category, i.unit as unit,
                   c.quantity_consumed as quantity_consumed
            FROM anomalies a
            JOIN items i ON a.item_id = i.id
            LEFT JOIN consumption_logs c ON a.consumption_log_id = c.id
            WHERE 1=1
        """
        params = []
        if status and status != "ALL":
            query += " AND a.status = ?"
            params.append(status)
        elif not status:
            # Default to unresolved
            query += " AND a.status = 'UNRESOLVED'"

        query += " ORDER BY a.id DESC"
        cursor.execute(query, params)
        rows = [dict_from_row(r) for r in cursor.fetchall()]
        return rows


@router.post("/detect-all")
def run_full_anomaly_scan():
    """
    Trigger a full machine learning & statistical anomaly detection scan across
    all inventory items and their consumption logs.
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items")
        items = [dict_from_row(r) for r in cursor.fetchall()]

        new_anomalies_count = 0
        now_iso = datetime.now().isoformat()

        for item in items:
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]

            detected = ml_engine.detect_anomalies(item, logs)

            for anom in detected:
                # Check if already recorded
                if anom.get("consumption_log_id"):
                    cursor.execute(
                        "SELECT id FROM anomalies WHERE consumption_log_id = ?",
                        (anom["consumption_log_id"],),
                    )
                else:
                    cursor.execute(
                        "SELECT id FROM anomalies WHERE item_id = ? AND description = ?",
                        (anom["item_id"], anom["description"]),
                    )

                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(
                        """
                        INSERT INTO anomalies (
                            item_id, consumption_log_id, anomaly_score, severity,
                            description, detected_at, status
                        ) VALUES (?, ?, ?, ?, ?, ?, 'UNRESOLVED')
                    """,
                        (
                            anom["item_id"],
                            anom.get("consumption_log_id"),
                            anom["anomaly_score"],
                            anom["severity"],
                            anom["description"],
                            now_iso,
                        ),
                    )
                    new_anomalies_count += 1

        return {
            "message": f"Full anomaly scan completed. Identified {new_anomalies_count} new anomaly alert(s).",
            "new_anomalies_detected": new_anomalies_count,
        }


@router.put("/{anomaly_id}/resolve")
def resolve_anomaly(anomaly_id: int, action: str = Query("ACKNOWLEDGED", pattern="^(ACKNOWLEDGED|DISMISSED)$")):
    """Update anomaly status to ACKNOWLEDGED or DISMISSED."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM anomalies WHERE id = ?", (anomaly_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Anomaly not found")

        cursor.execute("UPDATE anomalies SET status = ? WHERE id = ?", (action, anomaly_id))
        return {"message": f"Anomaly marked as {action}", "id": anomaly_id}
