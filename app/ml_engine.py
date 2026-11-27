import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sklearn.linear_model import Ridge
from sklearn.ensemble import IsolationForest


class SmartStockMLEngine:
    """
    Intelligent consumption forecasting, explainability generation,
    and anomaly detection engine for household inventory.
    """

    def __init__(self):
        self.random_state = 42

    # =========================================================================
    # REFILL PREDICTION & EXPLAINABILITY
    # =========================================================================

    def predict_refill(
        self,
        item: dict,
        consumption_history: List[dict],
        current_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Predicts when an item will deplete and requires a refill.
        Uses Scikit-learn Ridge regression with day-of-week & trend features
        when sufficient data is available, with statistical/rule-based fallbacks.
        """
        if current_date is None:
            current_date = datetime.now()

        current_qty = float(item["current_quantity"])
        min_threshold = float(item["min_threshold"])
        optimal_qty = float(item["optimal_quantity"])
        unit = item["unit"]

        # If item has 0 or negative quantity
        if current_qty <= 0:
            return {
                "daily_burn_rate": 0.0,
                "days_remaining": 0.0,
                "predicted_refill_date": current_date.strftime("%Y-%m-%d"),
                "urgency": "CRITICAL",
                "explainability": {
                    "algorithm_used": "Immediate Stockout Check",
                    "daily_burn_rate": 0.0,
                    "unit": unit,
                    "recent_trend": "Item is completely depleted",
                    "weekend_variation": "N/A",
                    "data_points_count": len(consumption_history),
                    "reasons": [
                        f"Item is currently out of stock (0.0 {unit}).",
                        f"Immediate restock of {optimal_qty} {unit} is required.",
                    ],
                    "confidence_score": 1.0,
                    "recommendation": f"Replenish {optimal_qty:.1f} {unit} immediately.",
                },
            }

        # Filter and prepare consumption data
        clean_logs = []
        for log in consumption_history:
            try:
                date_str = str(log["consumption_date"]).split(" ")[0].split("T")[0]
                qty = float(log["quantity_consumed"])
                if qty > 0:
                    clean_logs.append({"date": date_str, "quantity": qty, "is_waste": int(log.get("is_waste", 0))})
            except (ValueError, TypeError):
                continue

        num_points = len(clean_logs)

        # Fallback 1: No consumption logs at all (Pure Rule-Based Heuristic)
        if num_points == 0:
            # Assume a baseline 14-day depletion cycle from optimal to 0
            daily_burn_rate = max(optimal_qty / 14.0, 0.05)
            days_remaining = round(current_qty / daily_burn_rate, 1)
            refill_date = current_date + timedelta(days=int(np.ceil(days_remaining)))
            urgency = self._determine_urgency(days_remaining, current_qty, min_threshold)

            return {
                "daily_burn_rate": round(daily_burn_rate, 2),
                "days_remaining": days_remaining,
                "predicted_refill_date": refill_date.strftime("%Y-%m-%d"),
                "urgency": urgency,
                "explainability": {
                    "algorithm_used": "Rule-Based Heuristic (Category Baseline)",
                    "daily_burn_rate": round(daily_burn_rate, 2),
                    "unit": unit,
                    "recent_trend": "No consumption history recorded yet",
                    "weekend_variation": "Standard distribution assumed",
                    "data_points_count": 0,
                    "reasons": [
                        f"No prior consumption logs found for {item['name']}.",
                        f"Applied standard 14-day household turnover heuristic ({daily_burn_rate:.2f} {unit}/day).",
                    ],
                    "confidence_score": 0.40,
                    "recommendation": f"Log daily usage to train predictive ML models. Target restock: {optimal_qty - current_qty:.1f} {unit}.",
                },
            }

        # Aggregate daily consumption
        df = pd.DataFrame(clean_logs)
        df["date"] = pd.to_datetime(df["date"])
        daily_df = df.groupby("date")["quantity"].sum().reset_index()
        daily_df = daily_df.sort_values("date").reset_index(drop=True)
        unique_days = len(daily_df)

        # Fallback 2: 1 to 6 consumption days (Statistical Exponential Moving Average)
        if unique_days < 7:
            quantities = daily_df["quantity"].values
            # Exponentially weighted average with alpha = 0.35
            weights = np.array([(1 - 0.35) ** (len(quantities) - 1 - i) for i in range(len(quantities))])
            weights /= weights.sum()
            daily_burn_rate = float(np.sum(quantities * weights))
            daily_burn_rate = max(daily_burn_rate, 0.02)

            days_remaining = round(current_qty / daily_burn_rate, 1)
            refill_date = current_date + timedelta(days=int(np.ceil(days_remaining)))
            urgency = self._determine_urgency(days_remaining, current_qty, min_threshold)

            avg_qty = float(np.mean(quantities))
            trend_pct = ((daily_burn_rate - avg_qty) / avg_qty) * 100 if avg_qty > 0 else 0

            return {
                "daily_burn_rate": round(daily_burn_rate, 2),
                "days_remaining": days_remaining,
                "predicted_refill_date": refill_date.strftime("%Y-%m-%d"),
                "urgency": urgency,
                "explainability": {
                    "algorithm_used": "Weighted Exponential Moving Average (EMA)",
                    "daily_burn_rate": round(daily_burn_rate, 2),
                    "unit": unit,
                    "recent_trend": f"{trend_pct:+.1f}% weighted towards recent days",
                    "weekend_variation": "Awaiting more records for seasonality",
                    "data_points_count": unique_days,
                    "reasons": [
                        f"Based on {unique_days} consumption days averaging {avg_qty:.2f} {unit}/day.",
                        f"Exponential weighting places higher importance on recent usage ({daily_burn_rate:.2f} {unit}/day).",
                        f"Remaining stock ({current_qty:.1f} {unit}) will reach zero in approximately {days_remaining} days.",
                    ],
                    "confidence_score": round(0.60 + min(unique_days * 0.025, 0.15), 2),
                    "recommendation": f"Refill {optimal_qty - current_qty:.1f} {unit} by {refill_date.strftime('%b %d, %Y')} to maintain buffer.",
                },
            }

        # Full Scikit-learn Machine Learning Model (>= 7 distinct consumption days)
        daily_df["day_of_week"] = daily_df["date"].dt.dayofweek
        daily_df["is_weekend"] = daily_df["day_of_week"].apply(lambda x: 1 if x >= 5 else 0)
        start_date = daily_df["date"].min()
        daily_df["day_index"] = (daily_df["date"] - start_date).dt.days

        # Rolling 3-day average feature
        daily_df["rolling_3d"] = daily_df["quantity"].rolling(window=3, min_periods=1).mean()

        # Features: day_index, is_weekend, day_of_week, rolling_3d
        X = daily_df[["day_index", "is_weekend", "day_of_week", "rolling_3d"]].values
        y = daily_df["quantity"].values

        # Train Ridge model with L2 regularization
        model = Ridge(alpha=1.0, random_state=self.random_state)
        model.fit(X, y)

        # Predict next 7 days consumption taking future day-of-week into account
        future_burn_rates = []
        last_day_index = daily_df["day_index"].max()
        last_rolling = daily_df["rolling_3d"].iloc[-1]

        for step in range(1, 8):
            f_date = current_date + timedelta(days=step)
            f_dow = f_date.weekday()
            f_weekend = 1 if f_dow >= 5 else 0
            f_idx = last_day_index + step
            pred = model.predict([[f_idx, f_weekend, f_dow, last_rolling]])[0]
            future_burn_rates.append(max(float(pred), 0.05))

        daily_burn_rate = float(np.mean(future_burn_rates))
        days_remaining = round(current_qty / max(daily_burn_rate, 0.01), 1)
        refill_date = current_date + timedelta(days=int(np.ceil(days_remaining)))
        urgency = self._determine_urgency(days_remaining, current_qty, min_threshold)

        # Explainability & Feature Insights
        weekend_avg = daily_df[daily_df["is_weekend"] == 1]["quantity"].mean()
        weekday_avg = daily_df[daily_df["is_weekend"] == 0]["quantity"].mean()
        weekend_factor_str = "Even distribution across weekdays and weekends"
        if not np.isnan(weekend_avg) and not np.isnan(weekday_avg) and weekday_avg > 0:
            diff_ratio = (weekend_avg - weekday_avg) / weekday_avg
            if diff_ratio > 0.15:
                weekend_factor_str = f"Weekend usage is {diff_ratio * 100:.1f}% higher than weekdays"
            elif diff_ratio < -0.15:
                weekend_factor_str = f"Weekday usage is {abs(diff_ratio) * 100:.1f}% higher than weekends"

        # Recent 7-day trend vs overall mean
        overall_mean = float(daily_df["quantity"].mean())
        recent_7d_mean = float(daily_df.tail(7)["quantity"].mean())
        trend_ratio = ((recent_7d_mean - overall_mean) / overall_mean) * 100 if overall_mean > 0 else 0
        trend_str = f"{trend_ratio:+.1f}% vs 30-day baseline"

        # Model confidence score based on R-squared bounded [0.75, 0.95]
        score = model.score(X, y)
        confidence_score = round(max(0.75, min(0.95, 0.75 + score * 0.20)), 2)

        reasons = [
            f"Machine Learning model analyzed {unique_days} consumption cycles ({num_points} recorded logs).",
            f"Forecasted daily burn rate is {daily_burn_rate:.2f} {unit}/day (Trend: {trend_str}).",
            weekend_factor_str,
            f"Stock level ({current_qty:.1f} {unit}) crosses minimum safety buffer ({min_threshold} {unit}) in {max(0, round((current_qty - min_threshold) / max(daily_burn_rate, 0.01), 1))} days.",
        ]

        needed_restock = max(optimal_qty - current_qty, min_threshold)

        return {
            "daily_burn_rate": round(daily_burn_rate, 2),
            "days_remaining": days_remaining,
            "predicted_refill_date": refill_date.strftime("%Y-%m-%d"),
            "urgency": urgency,
            "explainability": {
                "algorithm_used": "Scikit-Learn Ridge Regression (Time-Decay & Seasonality)",
                "daily_burn_rate": round(daily_burn_rate, 2),
                "unit": unit,
                "recent_trend": trend_str,
                "weekend_variation": weekend_factor_str,
                "data_points_count": unique_days,
                "reasons": reasons,
                "confidence_score": confidence_score,
                "recommendation": f"Add {needed_restock:.1f} {unit} to shopping list before {refill_date.strftime('%b %d, %Y')}.",
            },
        }

    def _determine_urgency(self, days_remaining: float, current_qty: float, min_threshold: float) -> str:
        """Determines alert urgency level."""
        if current_qty <= min_threshold or days_remaining <= 2.0:
            return "CRITICAL"
        elif days_remaining <= 5.0:
            return "LOW"
        elif days_remaining <= 10.0:
            return "MODERATE"
        return "ADEQUATE"

    # =========================================================================
    # ANOMALY DETECTION ENGINE
    # =========================================================================

    def detect_anomalies(
        self,
        item: dict,
        consumption_history: List[dict],
    ) -> List[Dict[str, Any]]:
        """
        Detects anomalous consumption events (abnormal spikes, leakage, spillage,
        or perishable stagnation) using Scikit-Learn IsolationForest with
        IQR/Z-Score statistical fallback.
        """
        if not consumption_history:
            return []

        clean_records = []
        for log in consumption_history:
            try:
                clean_records.append({
                    "id": log["id"],
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "category": item["category"],
                    "quantity": float(log["quantity_consumed"]),
                    "unit": item["unit"],
                    "date": str(log["consumption_date"]),
                    "reason": log.get("reason", "Normal Usage"),
                    "is_waste": int(log.get("is_waste", 0)),
                })
            except (ValueError, KeyError, TypeError):
                continue

        if not clean_records:
            return []

        df = pd.DataFrame(clean_records)
        detected_anomalies = []

        # 1. Immediate Waste / Spoilage Anomaly check
        waste_records = df[df["is_waste"] == 1]
        for _, w in waste_records.iterrows():
            detected_anomalies.append({
                "item_id": item["id"],
                "item_name": item["name"],
                "category": item["category"],
                "consumption_log_id": int(w["id"]),
                "anomaly_score": 0.88,
                "severity": "HIGH",
                "description": f"Direct Waste/Spoilage reported: {w['quantity']:.2f} {item['unit']} discarded ({w['reason']}).",
                "detected_at": w["date"],
                "quantity_consumed": float(w["quantity"]),
                "unit": item["unit"],
            })

        # 2. Consumption Spike Detection
        quantities = df["quantity"].values
        num_logs = len(quantities)

        if num_logs >= 8:
            # IsolationForest Machine Learning Model
            features = []
            mean_q = float(np.mean(quantities))
            std_q = float(np.std(quantities)) if np.std(quantities) > 0 else 1.0

            for _, row in df.iterrows():
                try:
                    dt = pd.to_datetime(row["date"])
                    dow = dt.dayofweek
                except Exception:
                    dow = 0
                rel_val = (row["quantity"] - mean_q) / std_q
                features.append([row["quantity"], rel_val, dow])

            X = np.array(features)
            iso = IsolationForest(contamination=0.10, random_state=self.random_state)
            preds = iso.fit_predict(X)
            scores = -iso.score_samples(X)  # Higher score = more anomalous

            for idx, pred in enumerate(preds):
                if pred == -1 and df.iloc[idx]["quantity"] > mean_q:
                    row = df.iloc[idx]
                    multiplier = row["quantity"] / mean_q if mean_q > 0 else 2.0
                    if multiplier >= 2.0:
                        anomaly_score = float(scores[idx])
                        severity = "HIGH" if multiplier >= 3.0 else "MEDIUM"

                        # Avoid duplicate if already tagged as waste
                        if not any(a["consumption_log_id"] == int(row["id"]) for a in detected_anomalies):
                            detected_anomalies.append({
                                "item_id": item["id"],
                                "item_name": item["name"],
                                "category": item["category"],
                                "consumption_log_id": int(row["id"]),
                                "anomaly_score": round(anomaly_score, 2),
                                "severity": severity,
                                "description": f"Unusual Consumption Spike: {row['quantity']:.2f} {item['unit']} consumed ({multiplier:.1f}x higher than average {mean_q:.2f} {item['unit']}).",
                                "detected_at": row["date"],
                                "quantity_consumed": float(row["quantity"]),
                                "unit": item["unit"],
                            })
        else:
            # Statistical Fallback: IQR & Z-score
            q75, q25 = np.percentile(quantities, [75, 25])
            iqr = q75 - q25
            median = float(np.median(quantities))
            upper_bound = median + max(1.8 * iqr, 0.5 * median)

            for idx, row in df.iterrows():
                if row["quantity"] > upper_bound and row["quantity"] > 0:
                    multiplier = row["quantity"] / median if median > 0 else 2.0
                    severity = "HIGH" if multiplier >= 3.0 else ("MEDIUM" if multiplier >= 1.8 else "LOW")

                    if not any(a["consumption_log_id"] == int(row["id"]) for a in detected_anomalies):
                        detected_anomalies.append({
                            "item_id": item["id"],
                            "item_name": item["name"],
                            "category": item["category"],
                            "consumption_log_id": int(row["id"]),
                            "anomaly_score": round(min(0.95, 0.60 + (multiplier - 1) * 0.1), 2),
                            "severity": severity,
                            "description": f"Statistical Outlier: {row['quantity']:.2f} {item['unit']} is {multiplier:.1f}x typical median ({median:.2f} {item['unit']}).",
                            "detected_at": row["date"],
                            "quantity_consumed": float(row["quantity"]),
                            "unit": item["unit"],
                        })

        # 3. Perishable Food Waste Risk / Stagnation Alert
        expiry_str = item.get("expiry_date")
        current_qty = float(item["current_quantity"])
        if expiry_str and current_qty > 0:
            try:
                exp_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                now = datetime.now()
                days_to_exp = (exp_date - now).days
                if 0 <= days_to_exp <= 3:
                    detected_anomalies.append({
                        "item_id": item["id"],
                        "item_name": item["name"],
                        "category": item["category"],
                        "consumption_log_id": None,
                        "anomaly_score": 0.85,
                        "severity": "HIGH" if days_to_exp <= 1 else "MEDIUM",
                        "description": f"Imminent Expiry Alert: {current_qty:.1f} {item['unit']} remaining expires in {days_to_exp} day(s) on {expiry_str}. Prioritize consumption to avoid waste!",
                        "detected_at": now.strftime("%Y-%m-%d %H:%M"),
                        "quantity_consumed": None,
                        "unit": item["unit"],
                    })
            except Exception:
                pass

        return detected_anomalies


# Global ML Engine Instance
ml_engine = SmartStockMLEngine()
