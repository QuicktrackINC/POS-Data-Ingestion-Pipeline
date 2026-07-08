import os
import hmac
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from prisma import Prisma

from main import db

router = APIRouter(prefix="/api/internal/assistant", tags=["Internal Assistant"])

def validate_assistant_request(request: Request):
    api_key = request.headers.get("x-internal-api-key")
    request_source = request.headers.get("x-request-source")
    expected_key = os.getenv("INTERNAL_ASSISTANT_API_KEY")

    if not expected_key:
        raise HTTPException(status_code=503, detail="Service unavailable")

    if not api_key or not hmac.compare_digest(api_key.encode(), expected_key.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if request_source != "quicktrack-hub":
        raise HTTPException(status_code=403, detail="Forbidden")

    return True

@router.post("/recent-transactions", dependencies=[Depends(validate_assistant_request)])
async def get_recent_transactions():
    """Retrieve a summary of the latest POS transactions."""
    try:
        # Assuming `dailysalessummary` holds daily totals, or `saleslineitem` holds recent items.
        # We'll pull recent daily sales summaries as a stand-in for recent transactions if no specific transaction table exists.
        recent = await db.dailysalessummary.find_many(
            order={"businessDate": "desc"},
            take=10
        )
        result = []
        for r in recent:
            result.append({
                "storeCode": r.storeCode,
                "businessDate": r.businessDate,
                "grossSales": r.grossSales,
                "transactionCount": r.transactionCount,
                "cashAmount": r.cashAmount,
                "creditAmount": r.creditAmount,
            })
        return JSONResponse(content={"transactions": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store-daily-totals", dependencies=[Depends(validate_assistant_request)])
async def get_store_daily_totals(request: Request):
    """Retrieve aggregated sales totals for a specific store."""
    try:
        body = await request.json()
        store_code = body.get("storeCode")
        if not store_code:
            raise HTTPException(status_code=400, detail="Missing storeCode parameter")

        totals = await db.dailysalessummary.find_many(
            where={"storeCode": store_code},
            order={"businessDate": "desc"},
            take=10
        )
        result = []
        for t in totals:
            result.append({
                "businessDate": t.businessDate,
                "grossSales": t.grossSales,
                "netSales": t.netSales,
                "transactionCount": t.transactionCount,
                "fuelSales": t.fuelSales
            })
        return JSONResponse(content={"totals": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
