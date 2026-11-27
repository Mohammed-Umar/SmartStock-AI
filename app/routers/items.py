from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import ItemCreate, ItemUpdate, ItemResponse
from app.ml_engine import ml_engine

router = APIRouter(prefix="/api/items", tags=["Inventory Items"])


@router.get("", response_model=List[ItemResponse])
def get_items(
    search: Optional[str] = Query(None, description="Search item name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: Optional[str] = Query(None, description="ALL, LOW, CRITICAL, EXPIRING, GOOD"),
):
    """Retrieve all inventory items with dynamic status and ML prediction indicators."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM items WHERE 1=1"
        params = []

        if search:
            query += " AND name LIKE ?"
            params.append(f"%{search}%")
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY category ASC, name ASC"
        cursor.execute(query, params)
        raw_items = [dict_from_row(row) for row in cursor.fetchall()]

        # Attach ML burn-rate and days remaining
        results = []
        now = datetime.now()

        for item in raw_items:
            # Fetch recent consumption logs for ML prediction
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]
            prediction = ml_engine.predict_refill(item, logs, current_date=now)

            days_rem = prediction["days_remaining"]
            current_qty = item["current_quantity"]
            min_thresh = item["min_threshold"]

            # Compute stock status
            status = "GOOD"
            if current_qty <= 0:
                status = "OUT_OF_STOCK"
            elif current_qty <= min_thresh or days_rem <= 2.0:
                status = "CRITICAL"
            elif days_rem <= 5.0:
                status = "LOW"

            # Check expiry
            if item.get("expiry_date"):
                try:
                    exp_dt = datetime.strptime(item["expiry_date"], "%Y-%m-%d")
                    diff_days = (exp_dt - now).days
                    if 0 <= diff_days <= 3:
                        status = "EXPIRING_SOON"
                except Exception:
                    pass

            # Filter by status if specified
            if status_filter and status_filter != "ALL":
                if status_filter == "LOW" and status not in ["LOW", "CRITICAL", "OUT_OF_STOCK"]:
                    continue
                elif status_filter == "CRITICAL" and status not in ["CRITICAL", "OUT_OF_STOCK"]:
                    continue
                elif status_filter == "EXPIRING" and status != "EXPIRING_SOON":
                    continue
                elif status_filter == "GOOD" and status != "GOOD":
                    continue

            item["stock_status"] = status
            item["days_remaining"] = days_rem
            item["predicted_refill_date"] = prediction["predicted_refill_date"]
            results.append(item)

        return results


@router.get("/{item_id}")
def get_item_detail(item_id: int):
    """Retrieve item details, ML prediction breakdown, and recent consumption history."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        item_row = cursor.fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="Item not found")
        item = dict_from_row(item_row)

        cursor.execute(
            "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date DESC LIMIT 20",
            (item_id,),
        )
        logs = [dict_from_row(r) for r in cursor.fetchall()]

        # Generate ML prediction
        prediction = ml_engine.predict_refill(item, logs)

        return {
            "item": item,
            "prediction": prediction,
            "recent_logs": logs,
        }


@router.post("", response_model=ItemResponse)
def create_item(item: ItemCreate):
    """Create a new inventory item and record initial purchase."""
    now_iso = datetime.now().isoformat()
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO items (
                name, category, current_quantity, unit, min_threshold, optimal_quantity,
                cost_per_unit, purchase_date, expiry_date, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                item.name.strip(),
                item.category.strip(),
                item.current_quantity,
                item.unit.strip(),
                item.min_threshold,
                item.optimal_quantity,
                item.cost_per_unit,
                item.purchase_date,
                item.expiry_date,
                item.notes or "",
                now_iso,
                now_iso,
            ),
        )
        new_id = cursor.lastrowid

        # Also log to purchase_history
        cursor.execute(
            """
            INSERT INTO purchase_history (
                item_id, item_name, quantity, unit, cost, purchase_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                new_id,
                item.name.strip(),
                item.current_quantity,
                item.unit.strip(),
                round(item.current_quantity * item.cost_per_unit, 2),
                item.purchase_date,
                now_iso,
            ),
        )

        cursor.execute("SELECT * FROM items WHERE id = ?", (new_id,))
        created = dict_from_row(cursor.fetchone())
        created["stock_status"] = "GOOD"
        created["days_remaining"] = None
        created["predicted_refill_date"] = None
        return created


@router.put("/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item_update: ItemUpdate):
    """Update item details."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")

        current_data = dict_from_row(existing)
        update_data = item_update.model_dump(exclude_unset=True)

        if not update_data:
            return current_data

        now_iso = datetime.now().isoformat()
        update_data["updated_at"] = now_iso

        set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values())
        values.append(item_id)

        cursor.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)

        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        updated = dict_from_row(cursor.fetchone())
        return updated


@router.delete("/{item_id}")
def delete_item(item_id: int):
    """Delete an item and its associated logs from the database."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Item not found")

        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        return {"message": "Item successfully deleted", "item_id": item_id}
