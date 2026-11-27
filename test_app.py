from fastapi.testclient import TestClient
from main import app
from app.database import init_db, get_db_context
from app.seed_data import seed_database


def test_app_workflow():
    print("Initializing DB...")
    init_db()
    print("Seeding database...")
    seed_database(force=True)

    client = TestClient(app)

    # 1. Test Root Serve
    res = client.get("/")
    assert res.status_code == 200
    assert "SmartStock" in res.text
    print("✓ Root dashboard HTML served successfully.")

    # 2. Test Items Endpoint
    res = client.get("/api/items")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 10
    print(f"✓ Retrieved {len(items)} items from database with ML status.")

    # 3. Test Predictions Endpoint
    res = client.get("/api/predictions")
    assert res.status_code == 200
    preds = res.json()
    assert len(preds) >= 10
    first_pred = preds[0]
    assert "days_remaining" in first_pred
    assert "explainability" in first_pred
    assert len(first_pred["explainability"]["reasons"]) > 0
    print(f"✓ AI Predictions generated successfully. Top urgent item: {first_pred['item_name']} ({first_pred['days_remaining']} days remaining).")

    # 4. Test Anomalies Endpoint
    res = client.get("/api/anomalies?status=ALL")
    assert res.status_code == 200
    anomalies = res.json()
    assert len(anomalies) > 0
    print(f"✓ Anomaly detection verified. {len(anomalies)} anomalies identified.")

    # 5. Test Consumption Logging & Auto-Trigger
    first_item = items[0]
    initial_qty = first_item["current_quantity"]
    consume_payload = {
        "item_id": first_item["id"],
        "quantity_consumed": 0.2,
        "reason": "Test Suite Automated Consumption",
        "is_waste": False,
    }
    res = client.post("/api/consumption", json=consume_payload)
    assert res.status_code == 200
    log_data = res.json()
    assert log_data["quantity_consumed"] == 0.2

    # Check updated quantity in items
    res_item = client.get(f"/api/items/{first_item['id']}")
    assert res_item.status_code == 200
    updated_item = res_item.json()["item"]
    assert round(updated_item["current_quantity"], 2) == round(initial_qty - 0.2, 2)
    print(f"✓ Consumption logging verified. Quantity reduced from {initial_qty} to {updated_item['current_quantity']}.")

    # 6. Test Smart Shopping List & Duplicate Prevention
    res = client.get("/api/shopping")
    assert res.status_code == 200
    shop_list = res.json()
    print(f"✓ Retrieved {len(shop_list)} active shopping recommendations.")

    # Try to add an item that already exists in shopping list -> Expect duplicate error
    if len(shop_list) > 0:
        existing_shop_item = shop_list[0]
        duplicate_payload = {
            "item_id": existing_shop_item["item_id"],
            "item_name": existing_shop_item["item_name"],
            "category": existing_shop_item["category"],
            "quantity_needed": 2.0,
            "unit": existing_shop_item["unit"],
            "estimated_cost": 5.0,
            "urgency": "URGENT",
            "reason": "Duplicate test",
        }
        dup_res = client.post("/api/shopping", json=duplicate_payload)
        assert dup_res.status_code == 400
        assert "Duplicate Prevention Alert" in dup_res.json()["detail"]
        print("✓ Duplicate prevention guard correctly rejected duplicate shopping item!")

    # 7. Test Purchase & Restock
    if len(shop_list) > 0:
        target_shop = shop_list[0]
        if target_shop["item_id"]:
            # Check quantity before purchase
            before_item = client.get(f"/api/items/{target_shop['item_id']}").json()["item"]
            before_qty = before_item["current_quantity"]

            purchase_res = client.put(f"/api/shopping/{target_shop['id']}/purchase")
            assert purchase_res.status_code == 200

            after_item = client.get(f"/api/items/{target_shop['item_id']}").json()["item"]
            after_qty = after_item["current_quantity"]
            assert round(after_qty, 2) == round(before_qty + target_shop["quantity_needed"], 2)
            print(f"✓ Purchase & Restock cycle verified! Quantity automatically increased from {before_qty} to {after_qty}.")

    # 8. Test Dashboard Stats
    res = client.get("/api/analytics/dashboard")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_items"] >= 10
    print(f"✓ Dashboard stats verified: {stats}")

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY! 🚀")


if __name__ == "__main__":
    test_app_workflow()
