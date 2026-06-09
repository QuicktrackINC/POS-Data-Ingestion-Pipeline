"""
validators.py — XML validation before parsing.

Checks performed:
1. Is this valid XML?
2. Is the source type recognized?
3. Does it contain a business date?
4. Does it contain a store/location identifier?
5. Does it contain sales or item fields?
6. Are prices/totals numeric where expected?
"""

from __future__ import annotations

import re
from typing import Any


RECOGNIZED_SOURCE_TYPES = {
    "POSExport",
    "NAXML-ItemMaintenanceRequest",
}

# Validation error builder
def _err(error_type: str, message: str, field: str | None = None) -> dict:
    return {"errorType": error_type, "message": message, "field": field}


def validate_parsed_xml(
    parsed_data: dict[str, Any],
    filename: str,
) -> list[dict]:
    """
    Validate a parsed XML dict and return a list of error dicts.
    An empty list means validation passed.
    """
    errors: list[dict] = []

    if not parsed_data or not isinstance(parsed_data, dict):
        errors.append(_err("VALIDATION", "Parsed XML is empty or not a valid structure."))
        return errors

    root_keys = list(parsed_data.keys())
    if not root_keys:
        errors.append(_err("VALIDATION", "XML has no root element."))
        return errors

    source_type = root_keys[0]

    # ── 1. Recognized source type ────────────────────────────────────────────
    if source_type not in RECOGNIZED_SOURCE_TYPES:
        errors.append(_err(
            "VALIDATION",
            f"Unknown source format: '{source_type}'. Recognized: {', '.join(RECOGNIZED_SOURCE_TYPES)}",
            field="root_element",
        ))
        # We still continue to collect more errors

    root = parsed_data.get(source_type, {})

    # ── 2. POSExport-specific validation ─────────────────────────────────────
    if source_type == "POSExport":
        errors.extend(_validate_pos_export(root))

    # ── 3. ItemMaintenance-specific validation ────────────────────────────────
    elif source_type == "NAXML-ItemMaintenanceRequest":
        errors.extend(_validate_item_maintenance(root))

    return errors


def _validate_pos_export(root: dict) -> list[dict]:
    errors: list[dict] = []

    # Must have some kind of header or transaction block
    if not root:
        errors.append(_err("VALIDATION", "POSExport root is empty."))
        return errors

    # Business date — check common locations
    business_date = _extract_business_date_pos(root)
    if not business_date:
        errors.append(_err(
            "VALIDATION",
            "Could not detect business date. Expected fields: BusinessDate, Date, ReportDate, or Transaction Timestamp.",
            field="businessDate",
        ))

    # Store code — check common locations
    store_code = _extract_store_code_pos(root)
    if not store_code:
        errors.append(_err(
            "VALIDATION",
            "Could not detect store/location identifier. Expected fields: StoreID, LocationNumber, SiteNumber, StoreNumber.",
            field="storeCode",
        ))

    # Must have transactions or sales totals
    transactions = root.get("Transactions", {})
    if not transactions:
        # Try alternative keys
        transactions = root.get("Transaction") or root.get("Sales") or root.get("Items")

    if not transactions:
        errors.append(_err(
            "VALIDATION",
            "No transaction or sales data found in POSExport. Expected: Transactions, Sales.",
            field="Transactions",
        ))
    else:
        # Validate numeric fields inside transactions
        txn_list = transactions.get("Transaction", transactions) if isinstance(transactions, dict) else transactions
        if isinstance(txn_list, dict):
            txn_list = [txn_list]
        if isinstance(txn_list, list):
            for i, txn in enumerate(txn_list[:5]):  # check first 5 only
                errors.extend(_validate_numeric_txn_fields(txn, i))

    return errors


def _validate_item_maintenance(root: dict) -> list[dict]:
    errors: list[dict] = []

    if not root:
        errors.append(_err("VALIDATION", "ItemMaintenanceRequest root is empty."))
        return errors

    records = root.get("ItemRecord", [])
    if not records:
        errors.append(_err("VALIDATION", "No ItemRecord elements found.", field="ItemRecord"))
        return errors

    if isinstance(records, dict):
        records = [records]

    for i, rec in enumerate(records[:5]):
        if not rec.get("ItemCode") and not rec.get("UPC"):
            errors.append(_err(
                "VALIDATION",
                f"ItemRecord[{i}] missing ItemCode and UPC.",
                field="ItemCode",
            ))
        price_val = rec.get("Price")
        if price_val is not None and not _is_numeric(price_val):
            errors.append(_err(
                "VALIDATION",
                f"ItemRecord[{i}] Price is not numeric: '{price_val}'",
                field="Price",
            ))

    return errors


def _validate_numeric_txn_fields(txn: dict, index: int) -> list[dict]:
    errors: list[dict] = []
    for field in ("Total", "Tax", "GrandTotal"):
        val = txn.get(field)
        if val is not None and not _is_numeric(val):
            errors.append(_err(
                "VALIDATION",
                f"Transaction[{index}].{field} is not numeric: '{val}'",
                field=field,
            ))
    return errors


def _is_numeric(val: Any) -> bool:
    try:
        float(str(val).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


# ── Field extraction helpers (used by validator + normalizer) ─────────────────

def _extract_business_date_pos(root: dict) -> str | None:
    for key in ("BusinessDate", "Date", "ReportDate", "BusinessDay", "SalesDate"):
        v = root.get(key)
        if v:
            return str(v)
    # Try inside Header
    header = root.get("Header", {}) or {}
    for key in ("BusinessDate", "Date", "ReportDate"):
        v = header.get(key)
        if v:
            return str(v)
    # Try first transaction timestamp
    txns = root.get("Transactions", {})
    if isinstance(txns, dict):
        txn = txns.get("Transaction")
        if isinstance(txn, list) and txn:
            txn = txn[0]
        if isinstance(txn, dict):
            ts = txn.get("Timestamp") or txn.get("Date")
            if ts:
                # Extract date portion only
                return str(ts)[:10]
    return None


def _extract_store_code_pos(root: dict) -> str | None:
    for key in ("StoreID", "LocationNumber", "SiteNumber", "StoreNumber", "StoreCode", "Site"):
        v = root.get(key)
        if v:
            return str(v)
    # Try inside Header
    header = root.get("Header", {}) or {}
    for key in ("StoreID", "LocationNumber", "SiteNumber", "StoreNumber", "StoreCode"):
        v = header.get(key)
        if v:
            return str(v)
    return None
