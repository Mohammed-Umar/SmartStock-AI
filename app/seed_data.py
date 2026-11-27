import sqlite3
from datetime import datetime, timedelta
import random
from app.database import get_db_context
from app.ml_engine import ml_engine


def seed_database(force: bool = False):
    """
    Seeds the SQLite database with rich, realistic household inventory,
    historical consumption logs, purchases, anomalies, and shopping recommendations.
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Check if already seeded
        cursor.execute("SELECT COUNT(*) as count FROM items;")
        count = cursor.fetchone()["count"]
        if count > 0 and not force:
            return  # Already populated

        # If force, clear existing data
        if force:
            cursor.execute("DELETE FROM anomalies;")
            cursor.execute("DELETE FROM shopping_list;")
            cursor.execute("DELETE FROM purchase_history;")
            cursor.execute("DELETE FROM consumption_logs;")
            cursor.execute("DELETE FROM items;")

        now = datetime.now()
        base_date = now.date()

        # 1. SAMPLE ITEMS
        items_data = [
            {
                "name": "Fresh Whole Milk",
                "category": "Dairy & Eggs",
                "current_quantity": 0.6,
                "unit": "L",
                "min_threshold": 1.0,
                "optimal_quantity": 3.0,
                "cost_per_unit": 1.49,
                "purchase_date": (base_date - timedelta(days=5)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                "notes": "Farm-fresh pasteurized whole milk. Daily family staple.",
                "daily_base": 0.50,
                "weekend_boost": 0.35,
            },
            {
                "name": "Large Farm Eggs",
                "category": "Dairy & Eggs",
                "current_quantity": 3.0,
                "unit": "units",
                "min_threshold": 4.0,
                "optimal_quantity": 18.0,
                "cost_per_unit": 0.35,
                "purchase_date": (base_date - timedelta(days=9)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=12)).strftime("%Y-%m-%d"),
                "notes": "Free-range Grade A large eggs.",
                "daily_base": 1.5,
                "weekend_boost": 2.0,
            },
            {
                "name": "Basmati Long Grain Rice",
                "category": "Pantry & Grains",
                "current_quantity": 1.4,
                "unit": "kg",
                "min_threshold": 1.0,
                "optimal_quantity": 5.0,
                "cost_per_unit": 3.20,
                "purchase_date": (base_date - timedelta(days=35)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=330)).strftime("%Y-%m-%d"),
                "notes": "Aged aromatic royal basmati.",
                "daily_base": 0.18,
                "weekend_boost": 0.10,
            },
            {
                "name": "Extra Virgin Olive Oil",
                "category": "Pantry & Grains",
                "current_quantity": 0.15,
                "unit": "L",
                "min_threshold": 0.25,
                "optimal_quantity": 1.0,
                "cost_per_unit": 12.50,
                "purchase_date": (base_date - timedelta(days=40)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=250)).strftime("%Y-%m-%d"),
                "notes": "Cold-pressed Greek olive oil.",
                "daily_base": 0.035,
                "weekend_boost": 0.02,
            },
            {
                "name": "Artisan Sourdough Bread",
                "category": "Bakery & Fresh",
                "current_quantity": 4.0,
                "unit": "slices",
                "min_threshold": 4.0,
                "optimal_quantity": 16.0,
                "cost_per_unit": 0.28,
                "purchase_date": (base_date - timedelta(days=3)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=1)).strftime("%Y-%m-%d"),  # Expiring soon!
                "notes": "Bakery fresh rustic loaf. Perishable.",
                "daily_base": 2.5,
                "weekend_boost": 1.5,
            },
            {
                "name": "Colombian Dark Roast Coffee",
                "category": "Beverages",
                "current_quantity": 310.0,
                "unit": "g",
                "min_threshold": 150.0,
                "optimal_quantity": 500.0,
                "cost_per_unit": 0.035,
                "purchase_date": (base_date - timedelta(days=14)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=180)).strftime("%Y-%m-%d"),
                "notes": "Single origin whole bean coffee.",
                "daily_base": 24.0,
                "weekend_boost": 12.0,
            },
            {
                "name": "Organic Bananas",
                "category": "Fresh Produce",
                "current_quantity": 2.0,
                "unit": "units",
                "min_threshold": 3.0,
                "optimal_quantity": 8.0,
                "cost_per_unit": 0.40,
                "purchase_date": (base_date - timedelta(days=4)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
                "notes": "Fair trade ripe organic bananas.",
                "daily_base": 1.2,
                "weekend_boost": 0.5,
            },
            {
                "name": "Eco Laundry Detergent Pods",
                "category": "Cleaning & Household",
                "current_quantity": 9.0,
                "unit": "pods",
                "min_threshold": 10.0,
                "optimal_quantity": 45.0,
                "cost_per_unit": 0.45,
                "purchase_date": (base_date - timedelta(days=28)).strftime("%Y-%m-%d"),
                "expiry_date": None,
                "notes": "Plant-based stain fighting pods.",
                "daily_base": 0.45,
                "weekend_boost": 0.60,
            },
            {
                "name": "Concentrated Dishwashing Gel",
                "category": "Cleaning & Household",
                "current_quantity": 480.0,
                "unit": "ml",
                "min_threshold": 150.0,
                "optimal_quantity": 800.0,
                "cost_per_unit": 0.008,
                "purchase_date": (base_date - timedelta(days=20)).strftime("%Y-%m-%d"),
                "expiry_date": None,
                "notes": "Lemon scented grease-cutting gel.",
                "daily_base": 18.0,
                "weekend_boost": 6.0,
            },
            {
                "name": "Greek Strained Yogurt",
                "category": "Dairy & Eggs",
                "current_quantity": 180.0,
                "unit": "g",
                "min_threshold": 200.0,
                "optimal_quantity": 900.0,
                "cost_per_unit": 0.009,
                "purchase_date": (base_date - timedelta(days=6)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=4)).strftime("%Y-%m-%d"),
                "notes": "High-protein plain strained yogurt.",
                "daily_base": 120.0,
                "weekend_boost": 40.0,
            },
            {
                "name": "Organic Rolled Oats",
                "category": "Pantry & Grains",
                "current_quantity": 880.0,
                "unit": "g",
                "min_threshold": 300.0,
                "optimal_quantity": 1200.0,
                "cost_per_unit": 0.005,
                "purchase_date": (base_date - timedelta(days=18)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=200)).strftime("%Y-%m-%d"),
                "notes": "Whole grain rolled breakfast oats.",
                "daily_base": 45.0,
                "weekend_boost": 15.0,
            },
            {
                "name": "Natural Sparkling Water",
                "category": "Beverages",
                "current_quantity": 2.0,
                "unit": "bottles",
                "min_threshold": 3.0,
                "optimal_quantity": 12.0,
                "cost_per_unit": 1.15,
                "purchase_date": (base_date - timedelta(days=12)).strftime("%Y-%m-%d"),
                "expiry_date": (base_date + timedelta(days=120)).strftime("%Y-%m-%d"),
                "notes": "Zero-calorie crisp lime sparkling water.",
                "daily_base": 0.65,
                "weekend_boost": 0.50,
            },
        ]

        inserted_items = []
        for it in items_data:
            created_at = (now - timedelta(days=35)).isoformat()
            updated_at = now.isoformat()
            cursor.execute(
                """
                INSERT INTO items (
                    name, category, current_quantity, unit, min_threshold, optimal_quantity,
                    cost_per_unit, purchase_date, expiry_date, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    it["name"],
                    it["category"],
                    it["current_quantity"],
                    it["unit"],
                    it["min_threshold"],
                    it["optimal_quantity"],
                    it["cost_per_unit"],
                    it["purchase_date"],
                    it["expiry_date"],
                    it["notes"],
                    created_at,
                    updated_at,
                ),
            )
            item_id = cursor.lastrowid
            inserted_items.append({"id": item_id, **it})

        # 2. GENERATE HISTORICAL CONSUMPTION LOGS (Last 30 Days)
        random.seed(42)
        all_logs = []

        for item in inserted_items:
            item_id = item["id"]
            daily_base = item["daily_base"]
            weekend_boost = item["weekend_boost"]

            for day_offset in range(30, 0, -1):
                log_date = base_date - timedelta(days=day_offset)
                is_weekend = log_date.weekday() >= 5

                # Some days might have 0 consumption for discrete items like pods or bread
                if item["unit"] == "pods" and day_offset % 2 != 0 and not is_weekend:
                    continue

                # Normal consumption variation +/- 15%
                variance = random.uniform(0.85, 1.18)
                qty = (daily_base + (weekend_boost if is_weekend else 0)) * variance

                # Inject a couple of realistic anomalies in history:
                # A: Olive oil spillage on day -12 (0.4 L waste)
                is_waste = 0
                reason = "Normal Usage"

                if item["name"] == "Extra Virgin Olive Oil" and day_offset == 12:
                    qty = 0.40  # Massive spike
                    reason = "Kitchen Counter Accidental Spillage"
                    is_waste = 1
                elif item["name"] == "Colombian Dark Roast Coffee" and day_offset == 16:
                    qty = 140.0  # Massive spike
                    reason = "Weekend Family Brunch Gathering (12 guests)"
                elif item["name"] == "Artisan Sourdough Bread" and day_offset == 18:
                    qty = 3.0
                    reason = "Stale crust trimmed and discarded"
                    is_waste = 1

                qty = round(qty, 2)
                if qty <= 0:
                    continue

                created_ts = datetime.combine(log_date, datetime.min.time()).isoformat()

                cursor.execute(
                    """
                    INSERT INTO consumption_logs (
                        item_id, quantity_consumed, consumption_date, reason, is_waste, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        item_id,
                        qty,
                        log_date.strftime("%Y-%m-%d"),
                        reason,
                        is_waste,
                        created_ts,
                    ),
                )
                log_id = cursor.lastrowid
                all_logs.append({
                    "id": log_id,
                    "item_id": item_id,
                    "quantity_consumed": qty,
                    "consumption_date": log_date.strftime("%Y-%m-%d"),
                    "reason": reason,
                    "is_waste": is_waste,
                })

        # 3. GENERATE PURCHASE HISTORY (Past 2 Months)
        purchases = [
            ("Fresh Whole Milk", "Dairy & Eggs", 3.0, "L", 4.47, 5),
            ("Fresh Whole Milk", "Dairy & Eggs", 3.0, "L", 4.47, 14),
            ("Fresh Whole Milk", "Dairy & Eggs", 3.0, "L", 4.47, 22),
            ("Large Farm Eggs", "Dairy & Eggs", 18.0, "units", 6.30, 9),
            ("Large Farm Eggs", "Dairy & Eggs", 18.0, "units", 6.30, 25),
            ("Basmati Long Grain Rice", "Pantry & Grains", 5.0, "kg", 16.00, 35),
            ("Extra Virgin Olive Oil", "Pantry & Grains", 1.0, "L", 12.50, 40),
            ("Artisan Sourdough Bread", "Bakery & Fresh", 16.0, "slices", 4.48, 3),
            ("Artisan Sourdough Bread", "Bakery & Fresh", 16.0, "slices", 4.48, 11),
            ("Colombian Dark Roast Coffee", "Beverages", 500.0, "g", 17.50, 14),
            ("Colombian Dark Roast Coffee", "Beverages", 500.0, "g", 17.50, 45),
            ("Organic Bananas", "Fresh Produce", 8.0, "units", 3.20, 4),
            ("Organic Bananas", "Fresh Produce", 8.0, "units", 3.20, 12),
            ("Eco Laundry Detergent Pods", "Cleaning & Household", 45.0, "pods", 20.25, 28),
            ("Concentrated Dishwashing Gel", "Cleaning & Household", 800.0, "ml", 6.40, 20),
            ("Greek Strained Yogurt", "Dairy & Eggs", 900.0, "g", 8.10, 6),
            ("Organic Rolled Oats", "Pantry & Grains", 1200.0, "g", 6.00, 18),
            ("Natural Sparkling Water", "Beverages", 12.0, "bottles", 13.80, 12),
        ]

        for p_name, p_cat, p_qty, p_unit, p_cost, p_days_ago in purchases:
            p_date = (base_date - timedelta(days=p_days_ago)).strftime("%Y-%m-%d")
            # Find item_id if matches
            matching = [it["id"] for it in inserted_items if it["name"] == p_name]
            p_item_id = matching[0] if matching else None

            cursor.execute(
                """
                INSERT INTO purchase_history (
                    item_id, item_name, quantity, unit, cost, purchase_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    p_item_id,
                    p_name,
                    p_qty,
                    p_unit,
                    p_cost,
                    p_date,
                    p_date + "T10:00:00",
                ),
            )

        # 4. RUN ML ANOMALY DETECTION ON SEEDED DATA
        for item in inserted_items:
            item_logs = [l for l in all_logs if l["item_id"] == item["id"]]
            anomalies = ml_engine.detect_anomalies(item, item_logs)
            for anom in anomalies:
                cursor.execute(
                    """
                    INSERT INTO anomalies (
                        item_id, consumption_log_id, anomaly_score, severity,
                        description, detected_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'UNRESOLVED')
                """,
                    (
                        anom["item_id"],
                        anom["consumption_log_id"],
                        anom["anomaly_score"],
                        anom["severity"],
                        anom["description"],
                        anom["detected_at"],
                    ),
                )

        # 5. INITIAL SMART SHOPPING LIST RECOMMENDATIONS
        # Automatically generate recommendations for low-stock items
        for item in inserted_items:
            item_logs = [l for l in all_logs if l["item_id"] == item["id"]]
            prediction = ml_engine.predict_refill(item, item_logs)

            if prediction["urgency"] in ["CRITICAL", "LOW"]:
                needed = max(
                    round(item["optimal_quantity"] - item["current_quantity"], 1),
                    item["min_threshold"],
                )
                cost = round(needed * item["cost_per_unit"], 2)
                urgency = "URGENT" if prediction["urgency"] == "CRITICAL" else "RECOMMENDED"
                reason = f"Refill required. Stock ({item['current_quantity']} {item['unit']}) will deplete in {prediction['days_remaining']} days."

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
                        now.isoformat(),
                    ),
                )
