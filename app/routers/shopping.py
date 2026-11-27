from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import ShoppingItemCreate, ShoppingItemResponse
from app.ml_engine import ml_engine

router = APIRouter(prefix="/api/shopping", tags=["Smart Shopping List"])


@router.get("", response_model=List[ShoppingItemResponse])
def get_shopping_list(
    include_purchased: bool = Query(False, description="Whether to include already purchased items"),
):
    """Retrieve shopping list items, prioritized by urgency and duplicate prevention."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM shopping_list WHERE 1=1"
        if not include_purchased:
            query += " AND is_purchased = 0"
        query += " ORDER BY is_purchased ASC, CASE urgency WHEN 'URGENT' THEN 1 WHEN 'RECOMMENDED' THEN 2 ELSE 3 END, id DESC"

        cursor.execute(query)
        rows = [dict_from_row(r) for r in cursor.fetchall()]
        return rows


@router.post("/generate")
def auto_generate_recommendations():
    """
    AI Smart Recommendation Engine:
    - Scans all items and predicts depletion dates
    - Prevents duplicate buying by checking items already on active list
    - Recommends optimal purchase quantity based on burn rate and optimal stock
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items")
        items = [dict_from_row(r) for r in cursor.fetchall()]

        now_dt = datetime.now()
        added_count = 0
        skipped_duplicates = 0

        for item in items:
            # Check if active unpurchased item already exists
            cursor.execute(
                "SELECT id FROM shopping_list WHERE item_id = ? AND is_purchased = 0",
                (item["id"],),
            )
            if cursor.fetchone():
                skipped_duplicates += 1
                continue

            # Fetch consumption logs for ML prediction
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]
            pred = ml_engine.predict_refill(item, logs, current_date=now_dt)

            # Recommend if current stock <= min_threshold or depletion <= 5 days
            if pred["urgency"] in ["CRITICAL", "LOW"] or item["current_quantity"] <= item["min_threshold"]:
                needed = max(
                    round(item["optimal_quantity"] - item["current_quantity"], 1),
                    item["min_threshold"],
                )
                cost = round(needed * item["cost_per_unit"], 2)
                urgency = "URGENT" if pred["urgency"] == "CRITICAL" else "RECOMMENDED"
                reason = f"AI Predicted: Stock ({item['current_quantity']} {item['unit']}) depletes in {pred['days_remaining']} days (Refill by {pred['predicted_refill_date']})."

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
                        now_dt.isoformat(),
                    ),
                )
                added_count += 1

        return {
            "message": f"Generated {added_count} smart shopping recommendations ({skipped_duplicates} existing active items skipped to avoid duplicate purchases).",
            "added_count": added_count,
            "skipped_duplicates": skipped_duplicates,
        }


@router.post("", response_model=ShoppingItemResponse)
def add_shopping_item(item: ShoppingItemCreate):
    """
    Manually add an item to the shopping list with duplicate prevention check.
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Duplicate check: check if same item is already active
        if item.item_id:
            cursor.execute(
                "SELECT id, item_name FROM shopping_list WHERE item_id = ? AND is_purchased = 0",
                (item.item_id,),
            )
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate Prevention Alert: '{item.item_name}' is already on your active shopping list (ID #{existing['id']}).",
                )
        else:
            # Check by exact name
            cursor.execute(
                "SELECT id, item_name FROM shopping_list WHERE LOWER(item_name) = LOWER(?) AND is_purchased = 0",
                (item.item_name.strip(),),
            )
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate Prevention Alert: An item named '{item.item_name}' is already on your active shopping list.",
                )

        now_iso = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO shopping_list (
                item_id, item_name, category, quantity_needed, unit,
                estimated_cost, urgency, reason, is_purchased, auto_generated, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
        """,
            (
                item.item_id,
                item.item_name.strip(),
                item.category.strip(),
                item.quantity_needed,
                item.unit.strip(),
                item.estimated_cost,
                item.urgency,
                item.reason.strip(),
                now_iso,
            ),
        )
        new_id = cursor.lastrowid

        cursor.execute("SELECT * FROM shopping_list WHERE id = ?", (new_id,))
        return dict_from_row(cursor.fetchone())


@router.put("/{shopping_id}/purchase")
def mark_as_purchased(shopping_id: int):
    """
    Mark an item as purchased:
    - Sets is_purchased = 1
    - Automatically updates inventory current_quantity (restocks item)
    - Automatically logs new purchase record to purchase_history
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shopping_list WHERE id = ?", (shopping_id,))
        shop_row = cursor.fetchone()
        if not shop_row:
            raise HTTPException(status_code=404, detail="Shopping item not found")

        shop_item = dict_from_row(shop_row)
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        today_date = now_dt.strftime("%Y-%m-%d")

        cursor.execute("UPDATE shopping_list SET is_purchased = 1 WHERE id = ?", (shopping_id,))

        restocked_info = None

        # Restock inventory item if linked
        if shop_item.get("item_id"):
            cursor.execute("SELECT * FROM items WHERE id = ?", (shop_item["item_id"],))
            inv_row = cursor.fetchone()
            if inv_row:
                inv = dict_from_row(inv_row)
                new_qty = round(inv["current_quantity"] + shop_item["quantity_needed"], 2)
                cursor.execute(
                    "UPDATE items SET current_quantity = ?, purchase_date = ?, updated_at = ? WHERE id = ?",
                    (new_qty, today_date, now_iso, inv["id"]),
                )
                restocked_info = {
                    "item_id": inv["id"],
                    "item_name": inv["name"],
                    "previous_quantity": inv["current_quantity"],
                    "new_quantity": new_qty,
                    "unit": inv["unit"],
                }

        # Log to purchase history
        cursor.execute(
            """
            INSERT INTO purchase_history (
                item_id, item_name, quantity, unit, cost, purchase_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                shop_item.get("item_id"),
                shop_item["item_name"],
                shop_item["quantity_needed"],
                shop_item["unit"],
                shop_item["estimated_cost"],
                today_date,
                now_iso,
            ),
        )

        return {
            "message": f"Successfully purchased {shop_item['item_name']} and restocked inventory.",
            "shopping_id": shopping_id,
            "restocked": restocked_info,
        }


@router.delete("/{shopping_id}")
def delete_shopping_item(shopping_id: int):
    """Remove item from shopping list."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM shopping_list WHERE id = ?", (shopping_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Shopping item not found")

        cursor.execute("DELETE FROM shopping_list WHERE id = ?", (shopping_id,))
        return {"message": "Shopping item removed", "id": shopping_id}
