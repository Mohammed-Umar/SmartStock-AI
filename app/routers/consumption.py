from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import ConsumptionCreate, ConsumptionResponse, QuickConsumeRequest
from app.ml_engine import ml_engine

router = APIRouter(prefix="/api/consumption", tags=["Consumption Logging"])


@router.get("", response_model=List[ConsumptionResponse])
def get_consumption_logs(
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    is_waste_only: Optional[bool] = Query(False, description="Filter only food waste events"),
    limit: int = Query(50, ge=1, le=200),
):
    """Retrieve historical consumption logs."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = """
            SELECT c.*, i.name as item_name, i.category as category, i.unit as unit
            FROM consumption_logs c
            JOIN items i ON c.item_id = i.id
            WHERE 1=1
        """
        params = []
        if item_id:
            query += " AND c.item_id = ?"
            params.append(item_id)
        if is_waste_only:
            query += " AND c.is_waste = 1"

        query += " ORDER BY c.consumption_date DESC, c.id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = [dict_from_row(r) for r in cursor.fetchall()]
        return rows


@router.post("", response_model=ConsumptionResponse)
def log_consumption(consumption: ConsumptionCreate):
    """
    Log a consumption event:
    - Decrements current_quantity in items
    - Records log entry
    - Executes real-time anomaly detection
    - Automatically updates shopping recommendations if inventory turns low
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Check item exists
        cursor.execute("SELECT * FROM items WHERE id = ?", (consumption.item_id,))
        item_row = cursor.fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="Item not found")

        item = dict_from_row(item_row)
        now_dt = datetime.now()
        consump_date = consumption.consumption_date or now_dt.strftime("%Y-%m-%d")
        created_at = now_dt.isoformat()

        # Decrement quantity (minimum 0)
        new_qty = max(0.0, round(item["current_quantity"] - consumption.quantity_consumed, 2))
        cursor.execute(
            "UPDATE items SET current_quantity = ?, updated_at = ? WHERE id = ?",
            (new_qty, created_at, item["id"]),
        )

        # Insert log
        cursor.execute(
            """
            INSERT INTO consumption_logs (
                item_id, quantity_consumed, consumption_date, reason, is_waste, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                consumption.item_id,
                consumption.quantity_consumed,
                consump_date,
                consumption.reason or "Normal Usage",
                1 if consumption.is_waste else 0,
                created_at,
            ),
        )
        log_id = cursor.lastrowid

        # Update item object for ML checks
        item["current_quantity"] = new_qty

        # Fetch all logs for this item to check for anomalies
        cursor.execute(
            "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
            (item["id"],),
        )
        logs = [dict_from_row(r) for r in cursor.fetchall()]

        # Run Anomaly Detection
        anomalies = ml_engine.detect_anomalies(item, logs)
        for anom in anomalies:
            # Check if this specific log or condition was flagged
            if anom.get("consumption_log_id") == log_id:
                cursor.execute(
                    """
                    INSERT INTO anomalies (
                        item_id, consumption_log_id, anomaly_score, severity,
                        description, detected_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'UNRESOLVED')
                """,
                    (
                        item["id"],
                        log_id,
                        anom["anomaly_score"],
                        anom["severity"],
                        anom["description"],
                        created_at,
                    ),
                )

        # Check if item crossed threshold or is critically low -> Auto-add to Shopping List
        prediction = ml_engine.predict_refill(item, logs, current_date=now_dt)
        if prediction["urgency"] in ["CRITICAL", "LOW"]:
            # Check if not already in active shopping list
            cursor.execute(
                "SELECT id FROM shopping_list WHERE item_id = ? AND is_purchased = 0",
                (item["id"],),
            )
            already_in_list = cursor.fetchone()
            if not already_in_list:
                needed = max(
                    round(item["optimal_quantity"] - item["current_quantity"], 1),
                    item["min_threshold"],
                )
                cost = round(needed * item["cost_per_unit"], 2)
                urgency = "URGENT" if prediction["urgency"] == "CRITICAL" else "RECOMMENDED"
                reason = f"Refill trigger: Stock dropped to {new_qty} {item['unit']}. Estimated depletion in {prediction['days_remaining']} days."

                cursor.execute(
                    """
                    INSERT INTO shopping_list (
                        item_id, item_name, category, quantity_needed, unit,
                        estimated_cost, urgency, reason, is_purchased, auto_generated, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
                """,
                    (
                        item["id"],
                        item["name"],
                        item["category"],
                        needed,
                        item["unit"],
                        cost,
                        urgency,
                        reason,
                        created_at,
                    ),
                )

        # Return the created consumption log
        cursor.execute(
            """
            SELECT c.*, i.name as item_name, i.category as category, i.unit as unit
            FROM consumption_logs c
            JOIN items i ON c.item_id = i.id
            WHERE c.id = ?
        """,
            (log_id,),
        )
        created_log = dict_from_row(cursor.fetchone())
        return created_log


@router.post("/quick", response_model=ConsumptionResponse)
def quick_consume(req: QuickConsumeRequest):
    """Convenient endpoint to quickly log standard consumption with 1 click."""
    return log_consumption(
        ConsumptionCreate(
            item_id=req.item_id,
            quantity_consumed=req.quantity,
            reason="Quick Consume",
            is_waste=False,
        )
    )
