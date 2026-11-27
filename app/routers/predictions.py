from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import PredictionResponse
from app.ml_engine import ml_engine

router = APIRouter(prefix="/api/predictions", tags=["AI Refill Predictions"])


@router.get("", response_model=List[PredictionResponse])
def get_all_predictions():
    """
    Generate and return AI consumption and refill forecasts for all household items.
    Includes explainability reasons, model type, trend analysis, and urgency categorization.
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items ORDER BY name ASC")
        items = [dict_from_row(r) for r in cursor.fetchall()]

        now_dt = datetime.now()
        results = []

        for item in items:
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]

            pred = ml_engine.predict_refill(item, logs, current_date=now_dt)

            results.append({
                "item_id": item["id"],
                "item_name": item["name"],
                "category": item["category"],
                "current_quantity": item["current_quantity"],
                "unit": item["unit"],
                "min_threshold": item["min_threshold"],
                "optimal_quantity": item["optimal_quantity"],
                "daily_burn_rate": pred["daily_burn_rate"],
                "days_remaining": pred["days_remaining"],
                "predicted_refill_date": pred["predicted_refill_date"],
                "urgency": pred["urgency"],
                "explainability": pred["explainability"],
            })

        # Urgency priority sort: CRITICAL -> LOW -> MODERATE -> ADEQUATE
        urgency_order = {"CRITICAL": 0, "LOW": 1, "MODERATE": 2, "ADEQUATE": 3}
        results.sort(key=lambda x: (urgency_order.get(x["urgency"], 4), x["days_remaining"]))

        return results


@router.get("/{item_id}", response_model=PredictionResponse)
def get_item_prediction(item_id: int):
    """Retrieve detailed explainable prediction for a single item."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item_row = cursor.fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="Item not found")

        item = dict_from_row(item_row)
        cursor.execute(
            "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
            (item_id,),
        )
        logs = [dict_from_row(r) for r in cursor.fetchall()]

        pred = ml_engine.predict_refill(item, logs)

        return {
            "item_id": item["id"],
            "item_name": item["name"],
            "category": item["category"],
            "current_quantity": item["current_quantity"],
            "unit": item["unit"],
            "min_threshold": item["min_threshold"],
            "optimal_quantity": item["optimal_quantity"],
            "daily_burn_rate": pred["daily_burn_rate"],
            "days_remaining": pred["days_remaining"],
            "predicted_refill_date": pred["predicted_refill_date"],
            "urgency": pred["urgency"],
            "explainability": pred["explainability"],
        }
