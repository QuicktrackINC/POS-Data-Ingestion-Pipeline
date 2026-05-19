"""
FastAPI entry point — QuickTrack Integration Core v1.0.0

Full pipeline: Upload → Checksum → Validate → Normalize → Extract → Store → Export
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import xmltodict
from fastapi import Depends, FastAPI, File, HTTPException, Query, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from validators import validate_parsed_xml, _extract_business_date_pos, _extract_store_code_pos
from normalizer import (
    normalize_store_code, normalize_business_date,
    normalize_item, normalize_transaction, normalize_department, normalize_fuel_record,
    _safe_float, _safe_int,
)
from exporters import (
    build_daily_sales_csv, build_department_sales_csv, build_item_sales_csv,
    build_fuel_sales_csv, build_import_audit_csv, build_unknown_products_csv,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger("quicktrack_core")

# ---------------------------------------------------------------------------
# Prisma
# ---------------------------------------------------------------------------
from prisma import Prisma
db = Prisma()

PARSER_VERSION = "1.0.0"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    logger.info("Prisma connected to Neon PostgreSQL")
    
    # Ensure pg_trgm extension is available for fuzzy matching
    try:
        await db.execute_raw('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
        logger.info("pg_trgm extension verified")
    except Exception as e:
        logger.warning("Could not verify/create pg_trgm extension: %s", e)
        
    yield
    await db.disconnect()
    logger.info("Prisma disconnected")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="QuickTrack Integration Core",
    description="XML ingestion, validation, normalization, storage, and export layer.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
API_KEY_NAME = "X-API-Key"
INTERNAL_KEY_NAME = "x-internal-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
internal_key_header = APIKeyHeader(name=INTERNAL_KEY_NAME, auto_error=False)

VALID_API_KEY = os.environ.get("DATA_API_KEY", "dev-secret-key")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "internal-dev-key")

async def get_api_key(key: str = Security(api_key_header)):
    if key == VALID_API_KEY:
        return key
    raise HTTPException(status_code=401, detail="Invalid or missing API Key")

async def get_internal_key(key: str = Security(internal_key_header)):
    if key == INTERNAL_API_KEY:
        return key
    raise HTTPException(status_code=401, detail="Invalid or missing internal API key")

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root() -> dict:
    return {"status": "ok", "service": "QuickTrack Integration Core", "version": "1.0.0"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _log_event(import_id: str, st: str, note: str | None = None):
    await db.importevent.create(data={"importId": import_id, "status": st, "note": note})


async def _log_error(import_id: str, error_type: str, message: str, field: str | None = None):
    await db.importerror.create(data={
        "importId": import_id,
        "errorType": error_type,
        "message": message,
        "field": field,
    })


async def _update_status(import_id: str, st: str, **kwargs):
    await db.importrecord.update(where={"id": import_id}, data={"status": st, **kwargs})


# ---------------------------------------------------------------------------
# POST /api/upload-xml  — Full pipeline
# ---------------------------------------------------------------------------
@app.post("/api/upload-xml", status_code=201, tags=["Ingestion"], summary="Upload POS XML files")
async def upload_xml(files: list[UploadFile] = File(...)) -> dict:
    results = []

    for file in files:
        raw_bytes: bytes = await file.read()
        filename = file.filename or "unknown.xml"

        if not raw_bytes:
            results.append({"filename": filename, "status": "error", "message": "File is empty."})
            continue

        # ── 1. Checksum + duplicate detection ────────────────────────────────
        checksum = compute_checksum(raw_bytes)
        existing = await db.importrecord.find_first(where={"checksum": checksum})
        if existing:
            results.append({
                "filename": filename,
                "status": "duplicate",
                "message": f"Duplicate file detected. Previously uploaded on {existing.uploadedAt.strftime('%Y-%m-%d %H:%M')}.",
                "import_id": existing.id,
                "original_upload": existing.uploadedAt.isoformat(),
            })
            continue

        # ── 2. Create ImportRecord (UPLOADED) ─────────────────────────────────
        import_rec = await db.importrecord.create(data={
            "originalFileName": filename,
            "checksum": checksum,
            "fileSize": len(raw_bytes),
            "rawXml": raw_bytes.decode("utf-8", errors="replace"),
            "parserVersion": PARSER_VERSION,
            "status": "UPLOADED",
        })
        import_id = import_rec.id
        await _log_event(import_id, "UPLOADED", f"File received: {filename}")

        # ── 3. Parse XML ──────────────────────────────────────────────────────
        try:
            raw_xml = raw_bytes.decode("utf-8", errors="replace")
            parsed_data: dict = xmltodict.parse(raw_xml)
        except Exception as exc:
            await _update_status(import_id, "FAILED_VALIDATION", errorCount=1)
            await _log_error(import_id, "VALIDATION", f"Invalid XML: {exc}")
            await _log_event(import_id, "FAILED_VALIDATION", f"XML parse error: {exc}")
            results.append({"filename": filename, "status": "error", "import_id": import_id,
                            "message": f"Invalid XML: {exc}"})
            continue

        source_type = list(parsed_data.keys())[0] if parsed_data else None

        # ── 4. Validate ───────────────────────────────────────────────────────
        await _update_status(import_id, "VALIDATING", sourceType=source_type)
        await _log_event(import_id, "VALIDATING")

        validation_errors = validate_parsed_xml(parsed_data, filename)
        if validation_errors:
            await _update_status(import_id, "FAILED_VALIDATION", errorCount=len(validation_errors))
            for e in validation_errors:
                await _log_error(import_id, e["errorType"], e["message"], e.get("field"))
            await _log_event(import_id, "FAILED_VALIDATION", f"{len(validation_errors)} validation error(s)")
            results.append({
                "filename": filename, "status": "failed_validation", "import_id": import_id,
                "message": f"Validation failed with {len(validation_errors)} error(s).",
                "errors": validation_errors,
            })
            continue

        await _log_event(import_id, "VALIDATED")

        # Extract store + date after validation
        root = parsed_data.get(source_type, {})
        store_code = normalize_store_code(root) or _extract_store_code_pos(root)
        business_date = normalize_business_date(root) or _extract_business_date_pos(root)

        await _update_status(import_id, "PROCESSING",
                             storeCode=store_code, businessDate=business_date)
        await _log_event(import_id, "PROCESSING")

        # ── 5. Extract + normalize ────────────────────────────────────────────
        records_extracted = 0
        try:
            if source_type == "POSExport":
                records_extracted = await _process_pos_export_v2(import_id, root, store_code, business_date)
            elif source_type == "NAXML-ItemMaintenanceRequest":
                records_extracted = await _process_item_maintenance_v2(import_id, root, store_code)

            # Also persist legacy POSDataRecord for backward compat
            await db.posdatarecord.create(data={
                "source": "POS",
                "raw_xml": raw_xml,
                "parsed_data": json.dumps(parsed_data),
                "message_type": source_type,
            })

            await _update_status(import_id, "PROCESSED",
                                 recordsExtracted=records_extracted, errorCount=0)
            await _log_event(import_id, "PROCESSED", f"{records_extracted} records extracted")

            results.append({
                "filename": filename, "status": "success", "import_id": import_id,
                "message": "XML uploaded, validated, and processed successfully.",
                "source_type": source_type,
                "store_code": store_code,
                "business_date": business_date,
                "records_extracted": records_extracted,
                "parsed_data": parsed_data,
            })

        except Exception as exc:
            logger.error("Processing error for %s: %s", filename, exc)
            await _update_status(import_id, "FAILED_PROCESSING")
            await _log_error(import_id, "PROCESSING", str(exc))
            await _log_event(import_id, "FAILED_PROCESSING", str(exc))
            results.append({
                "filename": filename, "status": "error", "import_id": import_id,
                "message": f"Processing failed: {exc}",
            })

    return {"results": results}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

async def _process_pos_export_v2(import_id: str, root: dict, store_code: str | None, business_date: str | None) -> int:
    records = 0
    sc = store_code or "UNKNOWN"
    bd = business_date or "UNKNOWN"

    # ── Daily Sales Summary ───────────────────────────────────────────────────
    totals_raw = root.get("Totals") or root.get("DailySummary") or root.get("Summary") or {}
    if totals_raw:
        await db.dailysalessummary.create(data={
            "importId": import_id,
            "storeCode": sc,
            "businessDate": bd,
            "grossSales": _safe_float(totals_raw.get("GrossSales") or totals_raw.get("Total")),
            "netSales": _safe_float(totals_raw.get("NetSales") or totals_raw.get("Net")),
            "taxAmount": _safe_float(totals_raw.get("Tax") or totals_raw.get("TaxTotal")),
            "transactionCount": _safe_int(totals_raw.get("TransactionCount") or totals_raw.get("Transactions")),
            "cashAmount": _safe_float(totals_raw.get("Cash")),
            "creditAmount": _safe_float(totals_raw.get("Credit")),
            "debitAmount": _safe_float(totals_raw.get("Debit")),
            "ebtAmount": _safe_float(totals_raw.get("EBT")),
            "fuelSales": _safe_float(totals_raw.get("FuelSales")),
            "discountAmount": _safe_float(totals_raw.get("Discounts") or totals_raw.get("DiscountAmount")),
        })
        records += 1

    # ── Transactions → Line Items ─────────────────────────────────────────────
    txns_block = root.get("Transactions", {})
    txn_list = txns_block.get("Transaction", []) if isinstance(txns_block, dict) else []
    if isinstance(txn_list, dict):
        txn_list = [txn_list]

    txn_totals = {"gross": 0.0, "tax": 0.0, "count": 0}

    for txn in txn_list:
        norm_txn = normalize_transaction(txn)
        txn_totals["gross"] += norm_txn["grandTotal"]
        txn_totals["tax"] += norm_txn["tax"]
        txn_totals["count"] += 1

        items_block = txn.get("Items", {})
        items_list = items_block.get("Item", []) if isinstance(items_block, dict) else []
        if isinstance(items_list, dict):
            items_list = [items_list]

        for item in items_list:
            norm = normalize_item(item)
            
            # Check for existing mapping (normalization)
            alias = await db.productalias.find_first(where={"rawName": norm["itemName"]})
            master_id = alias.productMasterId if alias else None

            await db.saleslineitem.create(data={
                "importId": import_id,
                "storeCode": sc,
                "businessDate": bd,
                "transactionId": norm_txn["transactionId"],
                "itemName": norm["itemName"],
                "itemCode": norm["itemCode"],
                "upc": norm["upc"],
                "department": norm["department"],
                "quantity": norm["quantity"],
                "unitPrice": norm["price"],
                "salesAmount": norm["salesAmount"],
                "taxAmount": norm["taxAmount"],
                "productMasterId": master_id,
            })
            records += 1

            # Product extraction
            await _upsert_product_extract(import_id, sc, bd, norm, master_id)

        # Legacy sale upsert
        txn_id = norm_txn["transactionId"]
        if txn_id:
            try:
                ts_str = norm_txn["timestamp"]
                try:
                    ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
                except Exception:
                    ts = datetime.now()
                sale = await db.sale.upsert(
                    where={"transaction_id": txn_id},
                    data={
                        "create": {"transaction_id": txn_id, "timestamp": ts,
                                   "total": norm_txn["total"], "tax": norm_txn["tax"],
                                   "grand_total": norm_txn["grandTotal"],
                                   "payment_type": norm_txn["paymentType"]},
                        "update": {"timestamp": ts, "total": norm_txn["total"],
                                   "tax": norm_txn["tax"], "grand_total": norm_txn["grandTotal"],
                                   "payment_type": norm_txn["paymentType"]},
                    }
                )
                await db.saleitem.delete_many(where={"sale_id": sale.id})
                for item in items_list:
                    norm = normalize_item(item)
                    await db.saleitem.create(data={
                        "sale_id": sale.id,
                        "sku": norm["itemCode"] or norm["upc"] or "UNKNOWN",
                        "name": norm["itemName"],
                        "quantity": int(norm["quantity"]),
                        "price": norm["price"],
                    })
            except Exception as e:
                logger.warning("Legacy sale upsert failed: %s", e)

    # If no totals block but we have transactions, synthesize a daily summary
    if not totals_raw and txn_totals["count"] > 0:
        avg = txn_totals["gross"] / txn_totals["count"] if txn_totals["count"] else 0
        await db.dailysalessummary.create(data={
            "importId": import_id, "storeCode": sc, "businessDate": bd,
            "grossSales": round(txn_totals["gross"], 2),
            "taxAmount": round(txn_totals["tax"], 2),
            "transactionCount": txn_totals["count"],
            "averageTicket": round(avg, 2),
        })
        records += 1

    # ── Departments ───────────────────────────────────────────────────────────
    dept_block = root.get("Departments", {})
    dept_list = dept_block.get("Department", []) if isinstance(dept_block, dict) else []
    if isinstance(dept_list, dict):
        dept_list = [dept_list]
    for dept in dept_list:
        nd = normalize_department(dept)
        await db.departmentsummary.create(data={
            "importId": import_id, "storeCode": sc, "businessDate": bd,
            "department": nd["department"], "quantitySold": nd["quantitySold"],
            "grossAmount": nd["grossAmount"], "netAmount": nd["netAmount"],
            "taxAmount": nd["taxAmount"], "discountAmount": nd["discountAmount"],
        })
        records += 1

    # ── Fuel ──────────────────────────────────────────────────────────────────
    fuel_block = root.get("Fuel", {}) or root.get("FuelSales", {})
    fuel_list = fuel_block.get("Grade", []) if isinstance(fuel_block, dict) else []
    if isinstance(fuel_list, dict):
        fuel_list = [fuel_list]
    for f in fuel_list:
        nf = normalize_fuel_record(f)
        await db.fuelrecord.create(data={
            "importId": import_id, "storeCode": sc, "businessDate": bd,
            "fuelGrade": nf["fuelGrade"], "gallons": nf["gallons"],
            "salesAmount": nf["salesAmount"], "pricePerGallon": nf["pricePerGallon"],
            "pumpNumber": nf["pumpNumber"] or None,
        })
        records += 1

    return records


async def _process_item_maintenance_v2(import_id: str, root: dict, store_code: str | None) -> int:
    records = 0
    sc = store_code or "UNKNOWN"
    item_list = root.get("ItemRecord", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    for item in item_list:
        norm = normalize_item(item)
        item_code = norm["itemCode"] or norm["upc"]

        # Check for existing mapping
        alias = await db.productalias.find_first(where={"rawName": norm["itemName"]})
        master_id = alias.productMasterId if alias else None

        # ProductExtract
        await db.productextract.create(data={
            "importId": import_id, "storeCode": sc,
            "rawName": norm["itemName"], "itemCode": norm["itemCode"] or None,
            "upc": norm["upc"] or None, "department": norm["department"] or None,
            "unitPrice": norm["price"] if norm["price"] else None,
            "productMasterId": master_id,
        })
        records += 1

        # Legacy item upsert
        if item_code:
            try:
                await db.item.upsert(
                    where={"item_code": item_code},
                    data={
                        "create": {"item_code": item_code, "description": norm["itemName"],
                                   "price": norm["price"], "department_id": norm["department"] or None},
                        "update": {"description": norm["itemName"], "price": norm["price"],
                                   "department_id": norm["department"] or None},
                    }
                )
            except Exception as e:
                logger.warning("Legacy item upsert failed: %s", e)

    return records


async def _upsert_product_extract(import_id: str, store_code: str, business_date: str, norm: dict, master_id: str | None = None):
    raw_name = norm["itemName"]
    if not raw_name or raw_name == "Unknown Item":
        return
    await db.productextract.create(data={
        "importId": import_id, "storeCode": store_code, "businessDate": business_date,
        "rawName": raw_name, "itemCode": norm["itemCode"] or None,
        "upc": norm["upc"] or None, "department": norm["department"] or None,
        "unitPrice": norm["unitPrice"] if "unitPrice" in norm else norm.get("price"),
        "productMasterId": master_id,
    })
    # If not already mapped, track as UnknownProduct
    if not master_id:
        existing_unknown = await db.unknownproduct.find_first(
            where={"rawName": raw_name, "storeCode": store_code}
        )
        if existing_unknown:
            await db.unknownproduct.update(
                where={"id": existing_unknown.id},
                data={"occurrences": existing_unknown.occurrences + 1}
            )
        else:
            # Simple fuzzy logic: see if there's a suggested match based on other aliases
            # (In a real app, you'd use a more advanced fuzzy search)
            await db.unknownproduct.create(data={
                "rawName": raw_name, "storeCode": store_code, "businessDate": business_date,
            })


# ---------------------------------------------------------------------------
# GET /api/imports — Import History
# ---------------------------------------------------------------------------
@app.get("/api/imports", tags=["Imports"], summary="Get import history")
async def get_imports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    store_code: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[str] = Query(None),
) -> dict:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if status_filter:
        where["status"] = status_filter
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            where["uploadedAt"] = {"gte": dt}
        except ValueError:
            pass

    records = await db.importrecord.find_many(
        where=where, order={"uploadedAt": "desc"}, skip=skip, take=limit
    )
    total = await db.importrecord.count(where=where)

    return {
        "total": total, "skip": skip, "limit": limit,
        "imports": [_serialize_import(r) for r in records],
    }


# ---------------------------------------------------------------------------
# GET /api/imports/:id — Import Detail
# ---------------------------------------------------------------------------
@app.get("/api/imports/{import_id}", tags=["Imports"], summary="Get import detail")
async def get_import_detail(import_id: str) -> dict:
    rec = await db.importrecord.find_unique(
        where={"id": import_id},
        include={"events": True, "errors": True},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Import not found")

    daily = await db.dailysalessummary.find_many(where={"importId": import_id})
    line_items = await db.saleslineitem.find_many(where={"importId": import_id}, take=100)
    depts = await db.departmentsummary.find_many(where={"importId": import_id})
    fuels = await db.fuelrecord.find_many(where={"importId": import_id})

    return {
        "import": _serialize_import(rec),
        "timeline": [
            {"status": e.status, "note": e.note, "createdAt": e.createdAt.isoformat()}
            for e in sorted(rec.events, key=lambda x: x.createdAt)
        ],
        "errors": [
            {"errorType": e.errorType, "message": e.message, "field": e.field,
             "createdAt": e.createdAt.isoformat()}
            for e in rec.errors
        ],
        "extracted": {
            "dailySales": [_serialize_daily(d) for d in daily],
            "lineItems": [_serialize_line_item(li) for li in line_items],
            "departments": [_serialize_dept(d) for d in depts],
            "fuel": [_serialize_fuel(f) for f in fuels],
        },
        "rawXml": rec.rawXml,
    }


# ---------------------------------------------------------------------------
# POST /api/imports/:id/reprocess
# ---------------------------------------------------------------------------
@app.post("/api/imports/{import_id}/reprocess", tags=["Imports"], summary="Reprocess an import")
async def reprocess_import(import_id: str) -> dict:
    rec = await db.importrecord.find_unique(where={"id": import_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Import not found")
    if not rec.rawXml:
        raise HTTPException(status_code=400, detail="No raw XML stored for this import.")

    # Delete previously extracted records
    await db.dailysalessummary.delete_many(where={"importId": import_id})
    await db.saleslineitem.delete_many(where={"importId": import_id})
    await db.departmentsummary.delete_many(where={"importId": import_id})
    await db.fuelrecord.delete_many(where={"importId": import_id})
    await db.productextract.delete_many(where={"importId": import_id})
    await db.importerror.delete_many(where={"importId": import_id})

    await _update_status(import_id, "PROCESSING")
    await _log_event(import_id, "PROCESSING", "Reprocess triggered")

    try:
        parsed_data: dict = xmltodict.parse(rec.rawXml)
        source_type = list(parsed_data.keys())[0] if parsed_data else None
        root = parsed_data.get(source_type, {})
        store_code = normalize_store_code(root) or _extract_store_code_pos(root)
        business_date = normalize_business_date(root) or _extract_business_date_pos(root)

        records = 0
        if source_type == "POSExport":
            records = await _process_pos_export_v2(import_id, root, store_code, business_date)
        elif source_type == "NAXML-ItemMaintenanceRequest":
            records = await _process_item_maintenance_v2(import_id, root, store_code)

        await _update_status(import_id, "PROCESSED", recordsExtracted=records, errorCount=0,
                             parserVersion=PARSER_VERSION)
        await _log_event(import_id, "PROCESSED", f"Reprocessed — {records} records extracted")
        return {"status": "success", "import_id": import_id, "records_extracted": records}

    except Exception as exc:
        await _update_status(import_id, "FAILED_PROCESSING")
        await _log_error(import_id, "PROCESSING", str(exc))
        await _log_event(import_id, "FAILED_PROCESSING", str(exc))
        raise HTTPException(status_code=500, detail=f"Reprocess failed: {exc}")


# ---------------------------------------------------------------------------
# GET /api/dashboard — Operational Dashboard
# ---------------------------------------------------------------------------
@app.get("/api/dashboard", tags=["Dashboard"], summary="Operational ingestion dashboard metrics")
async def get_dashboard() -> dict:
    total = await db.importrecord.count()
    processed = await db.importrecord.count(where={"status": "PROCESSED"})
    failed = await db.importrecord.count(
        where={"status": {"in": ["FAILED_VALIDATION", "FAILED_PROCESSING"]}}
    )
    unknown_products = await db.unknownproduct.count()
    # Duplicate count = total files rejected as duplicate (not in import_records but we log them)
    # We can't count from DB easily, so we use difference check
    last_success = await db.importrecord.find_first(
        where={"status": "PROCESSED"}, order={"uploadedAt": "desc"}
    )
    return {
        "totalImports": total,
        "successfulImports": processed,
        "failedImports": failed,
        "lastSuccessfulImport": last_success.uploadedAt.isoformat() if last_success else None,
        "lastSuccessfulFile": last_success.originalFileName if last_success else None,
        "unknownProducts": unknown_products,
    }


# ---------------------------------------------------------------------------
# Export endpoints — CSV from normalized tables
# ---------------------------------------------------------------------------


def _xlsx_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def _export_response(data: str | bytes, filename: str, export_format: str) -> StreamingResponse:
    if export_format == "xlsx":
        return _xlsx_response(data, filename.replace(".csv", ".xlsx"))
    return _csv_response(data, filename)

def _csv_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/daily-sales", tags=["Export"], summary="Export daily sales CSV")
async def export_daily_sales(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if date:
        where["businessDate"] = date
    records = await db.dailysalessummary.find_many(where=where, order={"businessDate": "desc"})
    data = build_daily_sales_csv(records, export_format=export_format)
    return _export_response(data, f"daily_sales_{date or 'all'}_{store_code or 'all'}.csv", export_format)


@app.get("/api/export/department-sales", tags=["Export"], summary="Export department sales CSV")
async def export_department_sales(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if date:
        where["businessDate"] = date
    records = await db.departmentsummary.find_many(where=where, order={"businessDate": "desc"})
    data = build_department_sales_csv(records, export_format=export_format)
    return _export_response(data, f"dept_sales_{date or 'all'}.csv", export_format)


@app.get("/api/export/item-sales", tags=["Export"], summary="Export item/product sales CSV")
async def export_item_sales(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if date:
        where["businessDate"] = date
    records = await db.saleslineitem.find_many(where=where, order={"businessDate": "desc"}, take=5000)
    data = build_item_sales_csv(records, export_format=export_format)
    return _export_response(data, f"item_sales_{date or 'all'}.csv", export_format)


@app.get("/api/export/fuel-sales", tags=["Export"], summary="Export fuel sales CSV")
async def export_fuel_sales(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if date:
        where["businessDate"] = date
    records = await db.fuelrecord.find_many(where=where, order={"businessDate": "desc"})
    data = build_fuel_sales_csv(records, export_format=export_format)
    return _export_response(data, f"fuel_sales_{date or 'all'}.csv", export_format)


@app.get("/api/export/import-audit", tags=["Export"], summary="Export import audit CSV")
async def export_import_audit(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    if start_date:
        try:
            where["uploadedAt"] = {"gte": datetime.strptime(start_date, "%Y-%m-%d")}
        except ValueError:
            pass
    records = await db.importrecord.find_many(where=where, order={"uploadedAt": "desc"})
    data = build_import_audit_csv(records, export_format=export_format)
    return _export_response(data, "import_audit.csv", export_format)


@app.get("/api/export/unknown-products", tags=["Export"], summary="Export unknown products CSV")
async def export_unknown_products(
    export_format: str = Query('csv', alias='format'),
    store_code: Optional[str] = Query(None),
) -> StreamingResponse:
    where: dict = {}
    if store_code:
        where["storeCode"] = store_code
    records = await db.unknownproduct.find_many(where=where, order={"occurrences": "desc"})
    data = build_unknown_products_csv(records, export_format=export_format)
    return _export_response(data, "unknown_products.csv", export_format)


# ---------------------------------------------------------------------------
# Internal API — for Hub & Analytics
# ---------------------------------------------------------------------------

@app.get("/api/internal/imports", tags=["Internal API"])
async def internal_imports(
    skip: int = Query(0), limit: int = Query(50, le=200),
    _key: str = Depends(get_internal_key),
) -> dict:
    records = await db.importrecord.find_many(order={"uploadedAt": "desc"}, skip=skip, take=limit)
    total = await db.importrecord.count()
    return {"total": total, "imports": [_serialize_import(r) for r in records]}


@app.get("/api/internal/imports/{import_id}", tags=["Internal API"])
async def internal_import_detail(import_id: str, _key: str = Depends(get_internal_key)) -> dict:
    rec = await db.importrecord.find_unique(where={"id": import_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Import not found")
    return _serialize_import(rec)


@app.get("/api/internal/sales-summary", tags=["Internal API"])
async def internal_sales_summary(
    store_code: str = Query(...),
    date: str = Query(...),
    _key: str = Depends(get_internal_key),
) -> dict:
    records = await db.dailysalessummary.find_many(
        where={"storeCode": store_code, "businessDate": date}
    )
    return {"storeCode": store_code, "date": date,
            "summaries": [_serialize_daily(r) for r in records]}


@app.get("/api/internal/products/unknown", tags=["Internal API"])
async def internal_unknown_products(
    skip: int = Query(0), limit: int = Query(100, le=500),
    _key: str = Depends(get_internal_key),
) -> dict:
    records = await db.unknownproduct.find_many(
        order={"occurrences": "desc"}, skip=skip, take=limit
    )
    total = await db.unknownproduct.count()
    return {
        "total": total,
        "products": [
            {"id": r.id, "rawName": r.rawName, "storeCode": r.storeCode,
             "businessDate": r.businessDate, "occurrences": r.occurrences,
             "suggestedMatch": r.suggestedMatch, "createdAt": r.createdAt.isoformat()}
            for r in records
        ],
    }


# ---------------------------------------------------------------------------
# Product Normalization UI API
# ---------------------------------------------------------------------------

from pydantic import BaseModel

class ResolveProductRequest(BaseModel):
    unknown_product_id: str
    canonical_name: str
    upc: str | None = None
    department: str | None = None

@app.get("/api/products/unknown", tags=["Product Mapping"])
async def get_unknown_products(
    skip: int = Query(0), limit: int = Query(100, le=500),
) -> dict:
    total = await db.unknownproduct.count()
    
    # Use native PostgreSQL trigram matching (pg_trgm) for robust fuzzy search
    query = '''
    SELECT 
        u."id", 
        u."rawName", 
        u."storeCode", 
        u."businessDate", 
        u."occurrences", 
        u."suggestedMatch" as "existingSuggestion",
        u."createdAt",
        (
            SELECT m."canonicalName"
            FROM "product_masters" m
            WHERE similarity(m."canonicalName", u."rawName") > 0.2
            ORDER BY m."canonicalName" <-> u."rawName"
            LIMIT 1
        ) as "pgSuggestion"
    FROM "unknown_products" u
    ORDER BY u."occurrences" DESC
    LIMIT $1 OFFSET $2
    '''
    
    products = []
    try:
        raw_records = await db.query_raw(query, limit, skip)
        for r in raw_records:
            # We use existing suggestion if present, else fallback to pg_trgm suggestion
            sugg = r.get("existingSuggestion") or r.get("pgSuggestion")
            products.append({
                "id": r["id"], 
                "rawName": r["rawName"], 
                "storeCode": r.get("storeCode"),
                "businessDate": r.get("businessDate"), 
                "occurrences": r["occurrences"],
                "suggestedMatch": sugg, 
                "createdAt": r["createdAt"].isoformat() if hasattr(r["createdAt"], "isoformat") else r["createdAt"]
            })
    except Exception as e:
        logger.error("Error executing pg_trgm fuzzy search: %s", e)
        # Fallback to simple find_many if raw query fails (e.g. extension not installed)
        records = await db.unknownproduct.find_many(
            order={"occurrences": "desc"}, skip=skip, take=limit
        )
        products = [
            {
                "id": r.id, "rawName": r.rawName, "storeCode": r.storeCode,
                "businessDate": r.businessDate, "occurrences": r.occurrences,
                "suggestedMatch": r.suggestedMatch, "createdAt": r.createdAt.isoformat()
            } for r in records
        ]
        
    return {"total": total, "products": products}

@app.get("/api/products/master", tags=["Product Mapping"])
async def get_product_masters() -> dict:
    masters = await db.productmaster.find_many(order={"canonicalName": "asc"})
    return {"masters": [{"id": m.id, "canonicalName": m.canonicalName} for m in masters]}

@app.post("/api/products/resolve", tags=["Product Mapping"])
async def resolve_unknown_product(req: ResolveProductRequest) -> dict:
    unknown = await db.unknownproduct.find_unique(where={"id": req.unknown_product_id})
    if not unknown:
        raise HTTPException(status_code=404, detail="Unknown product not found")

    # Ensure canonical product master exists
    master = await db.productmaster.find_first(where={"canonicalName": req.canonical_name})
    if not master:
        master = await db.productmaster.create(data={
            "canonicalName": req.canonical_name,
            "upc": req.upc,
            "department": req.department,
        })
    else:
        # Update optional fields if provided and currently missing
        update_data = {}
        if req.upc and not master.upc:
            update_data["upc"] = req.upc
        if req.department and not master.department:
            update_data["department"] = req.department
        if update_data:
            master = await db.productmaster.update(
                where={"id": master.id}, data=update_data
            )

    # Create alias for the raw name
    existing_alias = await db.productalias.find_first(where={"rawName": unknown.rawName})
    if not existing_alias:
        await db.productalias.create(data={
            "rawName": unknown.rawName,
            "productMasterId": master.id
        })

    # ── UPDATE HISTORICAL DATA ───────────────────────────────────────────────
    # Link all existing SalesLineItems with this raw name to the new master
    await db.saleslineitem.update_many(
        where={"itemName": unknown.rawName},
        data={"productMasterId": master.id}
    )
    # Also update ProductExtracts
    await db.productextract.update_many(
        where={"rawName": unknown.rawName},
        data={"productMasterId": master.id}
    )

    # Delete ALL unknown product records with this exact rawName
    await db.unknownproduct.delete_many(where={"rawName": unknown.rawName})
    
    return {"status": "success", "message": "Product resolved", "master": {
        "id": master.id,
        "canonicalName": master.canonicalName,
    }}


# ---------------------------------------------------------------------------
# Analytics Engine (Normalized Data)
# ---------------------------------------------------------------------------

@app.get("/api/analytics/overview", tags=["Analytics"])
async def get_analytics_overview() -> dict:
    summaries = await db.dailysalessummary.find_many()
    total_rev = sum(s.grossSales for s in summaries)
    total_tax = sum(s.taxAmount for s in summaries)
    total_txns = sum(s.transactionCount for s in summaries)
    
    avg_ticket = total_rev / total_txns if total_txns > 0 else 0
    
    return {
        "summary": {
            "total_revenue": round(total_rev, 2),
            "total_tax": round(total_tax, 2),
            "transaction_count": total_txns,
            "average_ticket": round(avg_ticket, 2)
        }
    }

@app.get("/api/analytics/top-products", tags=["Analytics"])
async def get_top_products(limit: int = Query(5, ge=1, le=50)) -> dict:
    # Aggregating SalesLineItems by ProductMaster
    items = await db.saleslineitem.find_many(
        include={"productMaster": True}
    )
    
    velocity: dict = {}
    for li in items:
        # Use canonical name if available, else raw item name
        name = li.productMaster.canonicalName if li.productMaster else li.itemName
        if name not in velocity:
            velocity[name] = {"name": name, "quantity_sold": 0, "revenue": 0.0, "mapped": li.productMasterId is not None}
        velocity[name]["quantity_sold"] += li.quantity
        velocity[name]["revenue"] += li.salesAmount

    sorted_v = sorted(velocity.values(), key=lambda x: x["quantity_sold"], reverse=True)
    return {"data": sorted_v[:limit]}

@app.get("/api/analytics/recent-transactions", tags=["Analytics"])
async def get_recent_transactions(limit: int = Query(10, le=100)) -> dict:
    # Synthesize "Transactions" from SalesLineItems since we don't have a Transaction model in the new core (yet)
    # Actually, we can just show the most recent SalesLineItems as a feed.
    items = await db.saleslineitem.find_many(
        order={"createdAt": "desc"},
        take=limit,
        include={"productMaster": True}
    )
    return {
        "transactions": [
            {
                "id": i.id,
                "itemName": i.productMaster.canonicalName if i.productMaster else i.itemName,
                "rawName": i.itemName,
                "amount": i.salesAmount,
                "quantity": i.quantity,
                "storeCode": i.storeCode,
                "businessDate": i.businessDate,
                "mapped": i.productMasterId is not None
            }
            for i in items
        ]
    }


# ---------------------------------------------------------------------------
# Legacy endpoints (backward compatibility)
# ---------------------------------------------------------------------------

@app.get("/api/items", tags=["Catalog"])
async def get_items() -> dict:
    items = await db.item.find_many(order={"item_code": "asc"})
    return {"count": len(items), "items": [i.__dict__ for i in items]}


@app.get("/api/dashboard/sales", tags=["Sales"])
async def get_dashboard_sales() -> dict:
    sales = await db.sale.find_many(include={"items": True}, order={"timestamp": "desc"}, take=50)
    total_revenue = sum(s.grand_total for s in sales)
    total_tax = sum(s.tax for s in sales)
    return {
        "summary": {"total_revenue": round(total_revenue, 2),
                    "total_tax": round(total_tax, 2), "transaction_count": len(sales)},
        "sales": [{"id": s.id, "transaction_id": s.transaction_id,
                   "timestamp": s.timestamp, "grand_total": s.grand_total,
                   "payment_type": s.payment_type, "item_count": len(s.items)} for s in sales],
    }


@app.get("/api/sales-data", tags=["Sales"])
async def get_sales_data() -> dict:
    records = await db.posdatarecord.find_many(order={"created_at": "desc"}, take=50)
    sales_list = []
    for r in records:
        data = json.loads(r.parsed_data) if isinstance(r.parsed_data, str) else r.parsed_data
        sales_list.append({"id": r.id, "source": r.source,
                           "message_type": r.message_type, "created_at": r.created_at, "data": data})
    return {"meta": {"generated_at": datetime.now().isoformat(), "record_count": len(sales_list)},
            "sales": sales_list}


@app.get("/api/v1/sales", tags=["Sales Data API"])
async def get_sales_history(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
    start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    payment_type: Optional[str] = Query(None),
    api_key: str = Depends(get_api_key),
) -> dict:
    where_clause: dict = {}
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            date_filter["gte"] = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            date_filter["lte"] = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59)
        where_clause["timestamp"] = date_filter
    if payment_type:
        where_clause["payment_type"] = payment_type

    sales = await db.sale.find_many(
        where=where_clause, include={"items": True}, order={"timestamp": "desc"},
        skip=skip, take=limit,
    )
    total_count = await db.sale.count(where=where_clause)
    return {
        "meta": {"total_records": total_count, "skip": skip, "limit": limit},
        "data": [
            {"id": s.id, "transaction_id": s.transaction_id, "timestamp": s.timestamp.isoformat(),
             "total": s.total, "tax": s.tax, "grand_total": s.grand_total,
             "payment_type": s.payment_type,
             "items": [{"sku": i.sku, "name": i.name, "quantity": i.quantity,
                        "price": i.price} for i in s.items]}
            for s in sales
        ],
    }


@app.get("/api/v1/inventory/velocity", tags=["Inventory Data API"])
async def get_inventory_velocity(
    days: int = Query(30, ge=1, le=365), limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(get_api_key),
) -> dict:
    start_dt = datetime.now() - timedelta(days=days)
    sale_items = await db.saleitem.find_many(
        where={"sale": {"is": {"timestamp": {"gte": start_dt}}}}
    )
    velocity_map: dict = {}
    for si in sale_items:
        sku = si.sku
        if sku not in velocity_map:
            velocity_map[sku] = {"sku": sku, "name": si.name, "quantity_sold": 0, "revenue": 0.0}
        velocity_map[sku]["quantity_sold"] += si.quantity
        velocity_map[sku]["revenue"] += si.quantity * si.price
    sorted_items = sorted(velocity_map.values(), key=lambda x: x["quantity_sold"], reverse=True)
    return {
        "meta": {"days_analyzed": days, "start_date": start_dt.isoformat(),
                 "total_unique_items_sold": len(velocity_map)},
        "data": sorted_items[:limit],
    }


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_import(r) -> dict:
    return {
        "id": r.id,
        "originalFileName": r.originalFileName,
        "checksum": r.checksum,
        "fileSize": r.fileSize,
        "uploadedAt": r.uploadedAt.isoformat(),
        "uploadedBy": r.uploadedBy,
        "sourceType": r.sourceType,
        "storeCode": r.storeCode,
        "businessDate": r.businessDate,
        "parserVersion": r.parserVersion,
        "status": r.status,
        "recordsExtracted": r.recordsExtracted,
        "errorCount": r.errorCount,
        "updatedAt": r.updatedAt.isoformat() if r.updatedAt else None,
    }


def _serialize_daily(r) -> dict:
    return {
        "id": r.id, "storeCode": r.storeCode, "businessDate": r.businessDate,
        "grossSales": r.grossSales, "netSales": r.netSales, "taxAmount": r.taxAmount,
        "transactionCount": r.transactionCount, "averageTicket": r.averageTicket,
        "cashAmount": r.cashAmount, "creditAmount": r.creditAmount,
        "debitAmount": r.debitAmount, "ebtAmount": r.ebtAmount,
        "fuelSales": r.fuelSales, "discountAmount": r.discountAmount,
    }


def _serialize_line_item(r) -> dict:
    return {
        "id": r.id, "storeCode": r.storeCode, "businessDate": r.businessDate,
        "transactionId": r.transactionId, "itemName": r.itemName, "itemCode": r.itemCode,
        "upc": r.upc, "department": r.department, "quantity": r.quantity,
        "unitPrice": r.unitPrice, "salesAmount": r.salesAmount, "taxAmount": r.taxAmount,
    }


def _serialize_dept(r) -> dict:
    return {
        "id": r.id, "storeCode": r.storeCode, "businessDate": r.businessDate,
        "department": r.department, "quantitySold": r.quantitySold,
        "grossAmount": r.grossAmount, "netAmount": r.netAmount,
        "taxAmount": r.taxAmount, "discountAmount": r.discountAmount,
    }


def _serialize_fuel(r) -> dict:
    return {
        "id": r.id, "storeCode": r.storeCode, "businessDate": r.businessDate,
        "fuelGrade": r.fuelGrade, "gallons": r.gallons, "salesAmount": r.salesAmount,
        "pricePerGallon": r.pricePerGallon, "pumpNumber": r.pumpNumber,
    }
