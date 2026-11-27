from fastapi import APIRouter
from datetime import datetime
from app.database import get_db_context, dict_from_row
from app.models import DashboardStats
from app.ml_engine import ml_engine
from app.seed_data import seed_database

router = APIRouter(prefix="/api/analytics", tags=["Dashboard & Analytics"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_summary():
    """
    Returns high-level statistics for the main dashboard:
    - Total items
    - Low-stock count
    - Predicted refills count (< 5 days)
    - Monthly spending
    - Waste prevented metrics
    - Active anomaly count
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Total items
        cursor.execute("SELECT COUNT(*) as count FROM items")
        total_items = cursor.fetchone()["count"]

        # Active items and logs for prediction
        cursor.execute("SELECT * FROM items")
        items = [dict_from_row(r) for r in cursor.fetchall()]

        now_dt = datetime.now()
        low_stock_count = 0
        predicted_refills_count = 0

        for item in items:
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]
            pred = ml_engine.predict_refill(item, logs, current_date=now_dt)

            if item["current_quantity"] <= item["min_threshold"] or pred["days_remaining"] <= 2.0:
                low_stock_count += 1
            if pred["days_remaining"] <= 5.0:
                predicted_refills_count += 1

        # Monthly spending (current month)
        current_year_month = now_dt.strftime("%Y-%m")
        cursor.execute(
            "SELECT SUM(cost) as total FROM purchase_history WHERE purchase_date LIKE ?",
            (f"{current_year_month}%",),
        )
        spent_row = cursor.fetchone()
        monthly_spending = round(float(spent_row["total"] or 0.0), 2)

        # Active anomalies count
        cursor.execute("SELECT COUNT(*) as count FROM anomalies WHERE status = 'UNRESOLVED'")
        active_anomalies_count = cursor.fetchone()["count"]

        # Waste prevention calculation
        # Estimated based on items purchased on-demand vs spoilage prevented
        cursor.execute("SELECT COUNT(*) as count FROM shopping_list WHERE auto_generated = 1")
        smart_orders = cursor.fetchone()["count"]
        waste_prevented_units = round(smart_orders * 1.8, 1)
        waste_prevented_cost = round(smart_orders * 4.75, 2)

        return {
            "total_items": total_items,
            "low_stock_count": low_stock_count,
            "predicted_refills_count": predicted_refills_count,
            "monthly_spending": monthly_spending,
            "waste_prevented_units": waste_prevented_units,
            "waste_prevented_cost": waste_prevented_cost,
            "active_anomalies_count": active_anomalies_count,
            "currency_symbol": "$",
        }


@router.get("/spending")
def get_spending_charts():
    """
    Returns data for Chart.js:
    - Category spending breakdown
    - Monthly spending history (last 6 months)
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Category Breakdown
        cursor.execute("""
            SELECT i.category, SUM(p.cost) as total_cost
            FROM purchase_history p
            LEFT JOIN items i ON p.item_id = i.id
            GROUP BY i.category
            ORDER BY total_cost DESC
        """)
        cat_rows = cursor.fetchall()
        categories = []
        category_costs = []
        for r in cat_rows:
            cat_name = r["category"] or "General Groceries"
            categories.append(cat_name)
            category_costs.append(round(float(r["total_cost"]), 2))

        # Monthly Spending Trend (by month string YYYY-MM)
        cursor.execute("""
            SELECT substr(purchase_date, 1, 7) as month, SUM(cost) as total_cost
            FROM purchase_history
            GROUP BY month
            ORDER BY month ASC
            LIMIT 6
        """)
        month_rows = cursor.fetchall()
        months = [r["month"] for r in month_rows]
        monthly_costs = [round(float(r["total_cost"]), 2) for r in month_rows]

        return {
            "categories": categories,
            "category_costs": category_costs,
            "months": months,
            "monthly_costs": monthly_costs,
        }


@router.get("/stock-health")
def get_stock_health_chart():
    """
    Returns inventory stock distribution:
    Optimal, Adequate, Low, Critical, Expiring Soon.
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items")
        items = [dict_from_row(r) for r in cursor.fetchall()]

        now_dt = datetime.now()
        counts = {"Critical (<2 days)": 0, "Low (<5 days)": 0, "Moderate (5-10 days)": 0, "Adequate (>10 days)": 0}

        for item in items:
            cursor.execute(
                "SELECT * FROM consumption_logs WHERE item_id = ? ORDER BY consumption_date ASC",
                (item["id"],),
            )
            logs = [dict_from_row(r) for r in cursor.fetchall()]
            pred = ml_engine.predict_refill(item, logs, current_date=now_dt)

            urg = pred["urgency"]
            if urg == "CRITICAL":
                counts["Critical (<2 days)"] += 1
            elif urg == "LOW":
                counts["Low (<5 days)"] += 1
            elif urg == "MODERATE":
                counts["Moderate (5-10 days)"] += 1
            else:
                counts["Adequate (>10 days)"] += 1

        return {
            "labels": list(counts.keys()),
            "data": list(counts.values()),
        }


@router.post("/reset-demo")
def reset_demo_database():
    """Resets and reseeds database with fresh demonstration dataset."""
    seed_database(force=True)
    return {"message": "Database successfully reset and re-seeded with demo household data."}
