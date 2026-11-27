from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the item")
    category: str = Field(..., min_length=1, max_length=50, description="Item category")
    current_quantity: float = Field(..., ge=0, description="Current quantity in stock")
    unit: str = Field(..., min_length=1, max_length=20, description="Measurement unit (e.g., L, kg, packs)")
    min_threshold: float = Field(..., ge=0, description="Threshold below which item is flagged low-stock")
    optimal_quantity: float = Field(..., gt=0, description="Ideal target restock quantity")
    cost_per_unit: float = Field(..., ge=0, description="Unit cost/price")
    purchase_date: str = Field(..., description="Purchase date (YYYY-MM-DD)")
    expiry_date: Optional[str] = Field(None, description="Expiry date if applicable (YYYY-MM-DD)")
    notes: Optional[str] = Field("", description="Additional notes or specifications")


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    current_quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = None
    min_threshold: Optional[float] = Field(None, ge=0)
    optimal_quantity: Optional[float] = Field(None, gt=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    purchase_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None


class ItemResponse(ItemBase):
    id: int
    created_at: str
    updated_at: str
    stock_status: Optional[str] = "NORMAL"
    days_remaining: Optional[float] = None
    predicted_refill_date: Optional[str] = None


class ConsumptionCreate(BaseModel):
    item_id: int
    quantity_consumed: float = Field(..., gt=0, description="Amount consumed")
    consumption_date: Optional[str] = Field(None, description="Date of consumption (YYYY-MM-DD or ISO)")
    reason: Optional[str] = Field("Normal Usage", description="Usage reason (e.g., Cooking, Routine, Spoilage)")
    is_waste: Optional[bool] = Field(False, description="Whether this event was waste/spoilage")


class QuickConsumeRequest(BaseModel):
    item_id: int
    quantity: float = Field(..., gt=0)


class ConsumptionResponse(BaseModel):
    id: int
    item_id: int
    item_name: Optional[str] = None
    category: Optional[str] = None
    quantity_consumed: float
    unit: Optional[str] = None
    consumption_date: str
    reason: str
    is_waste: bool
    created_at: str


class ShoppingItemCreate(BaseModel):
    item_id: Optional[int] = None
    item_name: str
    category: str
    quantity_needed: float = Field(..., gt=0)
    unit: str
    estimated_cost: float = Field(..., ge=0)
    urgency: str = Field("RECOMMENDED", description="URGENT, RECOMMENDED, PLANNED")
    reason: str


class ShoppingItemResponse(BaseModel):
    id: int
    item_id: Optional[int] = None
    item_name: str
    category: str
    quantity_needed: float
    unit: str
    estimated_cost: float
    urgency: str
    reason: str
    is_purchased: bool
    auto_generated: bool
    created_at: str


class PredictionExplainability(BaseModel):
    algorithm_used: str
    daily_burn_rate: float
    unit: str
    recent_trend: str
    weekend_variation: str
    data_points_count: int
    reasons: List[str]
    confidence_score: float
    recommendation: str


class PredictionResponse(BaseModel):
    item_id: int
    item_name: str
    category: str
    current_quantity: float
    unit: str
    min_threshold: float
    optimal_quantity: float
    daily_burn_rate: float
    days_remaining: float
    predicted_refill_date: str
    urgency: str
    explainability: PredictionExplainability


class AnomalyResponse(BaseModel):
    id: int
    item_id: int
    item_name: str
    category: str
    consumption_log_id: Optional[int] = None
    anomaly_score: float
    severity: str
    description: str
    detected_at: str
    status: str
    quantity_consumed: Optional[float] = None
    unit: Optional[str] = None


class DashboardStats(BaseModel):
    total_items: int
    low_stock_count: int
    predicted_refills_count: int
    monthly_spending: float
    waste_prevented_units: float
    waste_prevented_cost: float
    active_anomalies_count: int
    currency_symbol: str = "$"
