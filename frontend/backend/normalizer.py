"""
normalizer.py — Field name normalization layer.

Maps the many different XML field names used by different POS vendors
into the canonical QuickTrack field names.

Canonical fields:
  storeCode, businessDate, itemName, itemCode, upc, department,
  price, quantity, salesAmount, taxAmount, fuelGrade
"""

from __future__ import annotations

from typing import Any


# ── Store code mappings ───────────────────────────────────────────────────────
_STORE_CODE_KEYS = [
    "StoreID", "LocationNumber", "SiteNumber", "StoreNumber",
    "StoreCode", "Site", "Location", "StoreId",
]

# ── Business date mappings ────────────────────────────────────────────────────
_BUSINESS_DATE_KEYS = [
    "BusinessDate", "Date", "ReportDate", "BusinessDay",
    "SalesDate", "TransactionDate",
]

# ── Item name mappings ────────────────────────────────────────────────────────
_ITEM_NAME_KEYS = [
    "ItemDescription", "Description", "ProductName", "Name",
    "ItemName", "Product", "Desc",
]

# ── Item code mappings ────────────────────────────────────────────────────────
_ITEM_CODE_KEYS = [
    "ItemCode", "SKU", "Sku", "ItemSKU", "PLU", "ItemPLU",
    "Code", "ProductCode",
]

# ── UPC mappings ─────────────────────────────────────────────────────────────
_UPC_KEYS = ["UPC", "Upc", "Barcode", "GTIN", "EAN"]

# ── Department mappings ───────────────────────────────────────────────────────
_DEPT_KEYS = [
    "DepartmentID", "Department", "DeptID", "Dept",
    "Category", "CategoryID", "DepartmentName",
]

# ── Price / amount mappings ───────────────────────────────────────────────────
_PRICE_KEYS = ["Price", "UnitPrice", "RegularPrice", "ItemPrice", "SellPrice"]
_QUANTITY_KEYS = ["Quantity", "Qty", "Units", "Count", "SoldQty"]
_SALES_AMOUNT_KEYS = ["SalesAmount", "Amount", "Total", "GrandTotal", "NetAmount"]
_TAX_KEYS = ["TaxAmount", "Tax", "TaxTotal"]
_FUEL_GRADE_KEYS = ["FuelGrade", "Grade", "GradeCode", "FuelType", "Product"]


def _first(d: dict, keys: list[str]) -> Any:
    """Return the first matching value from a dict given a priority key list."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(str(val).replace(",", "")))
    except (TypeError, ValueError):
        return default


def normalize_store_code(raw: dict) -> str | None:
    v = _first(raw, _STORE_CODE_KEYS)
    return str(v).strip() if v else None


def normalize_business_date(raw: dict) -> str | None:
    v = _first(raw, _BUSINESS_DATE_KEYS)
    if not v:
        return None
    return str(v).strip()[:10]  # Return YYYY-MM-DD portion only


def normalize_item(raw: dict) -> dict:
    """Normalize a raw item/product dict into canonical fields."""
    price = _safe_float(_first(raw, _PRICE_KEYS))
    quantity = _safe_float(_first(raw, _QUANTITY_KEYS), 1.0)
    sales_amount = _first(raw, _SALES_AMOUNT_KEYS)
    
    if sales_amount is None:
        sales_amount = price * quantity
    else:
        sales_amount = _safe_float(sales_amount)

    return {
        "itemName": str(_first(raw, _ITEM_NAME_KEYS) or "Unknown Item"),
        "itemCode": str(_first(raw, _ITEM_CODE_KEYS) or ""),
        "upc": str(_first(raw, _UPC_KEYS) or ""),
        "department": str(_first(raw, _DEPT_KEYS) or ""),
        "price": price,
        "quantity": quantity,
        "salesAmount": sales_amount,
        "taxAmount": _safe_float(_first(raw, _TAX_KEYS)),
    }


def normalize_transaction(raw: dict) -> dict:
    """Normalize a raw transaction dict into canonical fields."""
    return {
        "transactionId": str(raw.get("@ID") or raw.get("ID") or raw.get("TransactionID") or ""),
        "total": _safe_float(raw.get("Total")),
        "tax": _safe_float(raw.get("Tax") or raw.get("TaxAmount") or raw.get("TaxTotal")),
        "grandTotal": _safe_float(raw.get("GrandTotal") or raw.get("Total")),
        "paymentType": str(raw.get("PaymentType") or raw.get("TenderType") or raw.get("Payment") or "Unknown"),
        "timestamp": str(raw.get("Timestamp") or raw.get("Date") or raw.get("DateTime") or ""),
    }


def normalize_department(raw: dict) -> dict:
    """Normalize a raw department record."""
    return {
        "department": str(_first(raw, _DEPT_KEYS) or "Unknown"),
        "quantitySold": _safe_float(_first(raw, _QUANTITY_KEYS)),
        "grossAmount": _safe_float(raw.get("GrossAmount") or raw.get("Amount") or raw.get("Total")),
        "netAmount": _safe_float(raw.get("NetAmount") or raw.get("Net")),
        "taxAmount": _safe_float(_first(raw, _TAX_KEYS)),
        "discountAmount": _safe_float(raw.get("DiscountAmount") or raw.get("Discount")),
    }


def normalize_fuel_record(raw: dict) -> dict:
    """Normalize a raw fuel record."""
    return {
        "fuelGrade": str(_first(raw, _FUEL_GRADE_KEYS) or "Unknown"),
        "gallons": _safe_float(raw.get("Gallons") or raw.get("Volume") or raw.get("Qty")),
        "salesAmount": _safe_float(raw.get("SalesAmount") or raw.get("Amount") or raw.get("Total")),
        "pricePerGallon": _safe_float(raw.get("PricePerGallon") or raw.get("UnitPrice") or raw.get("Price")),
        "pumpNumber": str(raw.get("PumpNumber") or raw.get("Pump") or ""),
    }
