"""
exporters.py — CSV export generators for QuickTrack Integration Core.

All exports read from normalized database tables (not raw XML).
Each export returns a StreamingResponse with a CSV file.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
import pandas as pd
from typing import Any



def _make_xlsx_response(rows: list[dict], fieldnames: list[str]) -> bytes:
    df = pd.DataFrame(rows, columns=fieldnames)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Export')
    return buf.getvalue()

def _make_csv_response(rows: list[dict], fieldnames: list[str]) -> str:
    """Serialize a list of dicts to CSV string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


# ─── Daily Sales Export ───────────────────────────────────────────────────────

DAILY_SALES_FIELDS = [
    "Store", "BusinessDate", "GrossSales", "NetSales", "Tax",
    "Transactions", "AverageTicket", "Cash", "Credit", "Debit",
    "EBT", "FuelSales", "Discounts", "ExportedAt",
]


def build_daily_sales_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    """Build daily sales CSV from DailySalesSummary records."""
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "Store": r.storeCode,
            "BusinessDate": r.businessDate,
            "GrossSales": round(r.grossSales, 2),
            "NetSales": round(r.netSales, 2),
            "Tax": round(r.taxAmount, 2),
            "Transactions": r.transactionCount,
            "AverageTicket": round(r.averageTicket, 2),
            "Cash": round(r.cashAmount, 2),
            "Credit": round(r.creditAmount, 2),
            "Debit": round(r.debitAmount, 2),
            "EBT": round(r.ebtAmount, 2),
            "FuelSales": round(r.fuelSales, 2),
            "Discounts": round(r.discountAmount, 2),
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, DAILY_SALES_FIELDS)
    return _make_csv_response(rows, DAILY_SALES_FIELDS)


# ─── Department Sales Export ──────────────────────────────────────────────────

DEPT_SALES_FIELDS = [
    "Store", "BusinessDate", "Department", "QuantitySold",
    "GrossAmount", "NetAmount", "Tax", "Discounts", "ExportedAt",
]


def build_department_sales_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "Store": r.storeCode,
            "BusinessDate": r.businessDate,
            "Department": r.department,
            "QuantitySold": round(r.quantitySold, 2),
            "GrossAmount": round(r.grossAmount, 2),
            "NetAmount": round(r.netAmount, 2),
            "Tax": round(r.taxAmount, 2),
            "Discounts": round(r.discountAmount, 2),
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, DEPT_SALES_FIELDS)
    return _make_csv_response(rows, DEPT_SALES_FIELDS)


# ─── Item/Product Sales Export ────────────────────────────────────────────────

ITEM_SALES_FIELDS = [
    "Store", "BusinessDate", "ItemName", "ItemCode", "UPC",
    "Department", "Quantity", "UnitPrice", "SalesAmount", "Tax", "ExportedAt",
]


def build_item_sales_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "Store": r.storeCode,
            "BusinessDate": r.businessDate,
            "ItemName": r.itemName,
            "ItemCode": r.itemCode,
            "UPC": r.upc,
            "Department": r.department,
            "Quantity": round(r.quantity, 2),
            "UnitPrice": round(r.unitPrice, 2),
            "SalesAmount": round(r.salesAmount, 2),
            "Tax": round(r.taxAmount, 2),
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, ITEM_SALES_FIELDS)
    return _make_csv_response(rows, ITEM_SALES_FIELDS)


# ─── Fuel Sales Export ────────────────────────────────────────────────────────

FUEL_SALES_FIELDS = [
    "Store", "BusinessDate", "FuelGrade", "Gallons",
    "SalesAmount", "PricePerGallon", "Pump", "ExportedAt",
]


def build_fuel_sales_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "Store": r.storeCode,
            "BusinessDate": r.businessDate,
            "FuelGrade": r.fuelGrade,
            "Gallons": round(r.gallons, 3),
            "SalesAmount": round(r.salesAmount, 2),
            "PricePerGallon": round(r.pricePerGallon, 3),
            "Pump": r.pumpNumber,
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, FUEL_SALES_FIELDS)
    return _make_csv_response(rows, FUEL_SALES_FIELDS)


# ─── Import Audit Export ──────────────────────────────────────────────────────

IMPORT_AUDIT_FIELDS = [
    "ImportID", "FileName", "Store", "BusinessDate", "SourceType",
    "UploadTime", "Status", "ErrorCount", "RecordsExtracted",
    "UploadedBy", "Checksum", "FileSize", "ExportedAt",
]


def build_import_audit_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "ImportID": r.id,
            "FileName": r.originalFileName,
            "Store": r.storeCode or "",
            "BusinessDate": r.businessDate or "",
            "SourceType": r.sourceType or "",
            "UploadTime": r.uploadedAt.strftime("%Y-%m-%dT%H:%M:%S") if r.uploadedAt else "",
            "Status": r.status,
            "ErrorCount": r.errorCount,
            "RecordsExtracted": r.recordsExtracted,
            "UploadedBy": r.uploadedBy,
            "Checksum": r.checksum,
            "FileSize": r.fileSize,
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, IMPORT_AUDIT_FIELDS)
    return _make_csv_response(rows, IMPORT_AUDIT_FIELDS)


# ─── Unknown Products Export ──────────────────────────────────────────────────

UNKNOWN_PRODUCTS_FIELDS = [
    "RawProductName", "Store", "BusinessDate", "Occurrences",
    "SuggestedMatch", "CreatedAt", "ExportedAt",
]


def build_unknown_products_csv(records: list[Any], export_format: str = 'csv') -> str | bytes:
    exported_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for r in records:
        rows.append({
            "RawProductName": r.rawName,
            "Store": r.storeCode or "",
            "BusinessDate": r.businessDate or "",
            "Occurrences": r.occurrences,
            "SuggestedMatch": r.suggestedMatch or "",
            "CreatedAt": r.createdAt.strftime("%Y-%m-%dT%H:%M:%S") if r.createdAt else "",
            "ExportedAt": exported_at,
        })
    if export_format == 'xlsx':
        return _make_xlsx_response(rows, UNKNOWN_PRODUCTS_FIELDS)
    return _make_csv_response(rows, UNKNOWN_PRODUCTS_FIELDS)
