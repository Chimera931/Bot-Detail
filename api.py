import json
from aiohttp import web
from datetime import datetime, timedelta
import aiosqlite
import logging

from database import DB_PATH, add_block, remove_blocks_on_date
from config import ADMIN_ID

logger = logging.getLogger(__name__)

# Simple CORS helper
def cors_response(data=None, status=200, text=None):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }
    if text is not None:
        return web.Response(text=text, status=status, headers=headers, content_type="application/json")
    
    body = json.dumps(data) if data is not None else ""
    return web.Response(text=body, status=status, headers=headers, content_type="application/json")

async def options_handler(request):
    return cors_response(status=204)

async def get_schedule(request):
    """Return all appointments and blocks in a 30-day window."""
    try:
        now = datetime.now()
        start_s = now.strftime("%Y-%m-%d 00:00")
        end_s = (now + timedelta(days=35)).strftime("%Y-%m-%d 23:59")
        
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Get appointments
            async with db.execute("""
                SELECT a.*, c.phone, c.car_brand, c.car_body_name, c.plate_number
                FROM appointments a
                JOIN clients c ON a.client_id = c.telegram_id
                WHERE a.status NOT IN ('cancelled')
                  AND a.start_dt < ? AND a.end_dt > ?
            """, (end_s, start_s)) as cursor:
                appts = [dict(r) for r in await cursor.fetchall()]
                
            # Get blocks
            async with db.execute("""
                SELECT * FROM blocks
                WHERE start_dt < ? AND end_dt > ?
            """, (end_s, start_s)) as cursor:
                blocks = [dict(r) for r in await cursor.fetchall()]
                
        return cors_response({
            "appointments": appts,
            "blocks": blocks
        })
    except Exception as e:
        logger.exception("Error getting schedule")
        return cors_response({"error": str(e)}, status=500)

async def block_time(request):
    """Add a block for a date or specific interval."""
    try:
        data = await request.json()
        start_dt = data.get("start_dt") # YYYY-MM-DD HH:MM
        end_dt = data.get("end_dt")     # YYYY-MM-DD HH:MM
        reason = data.get("reason", "Занято")
        
        if not start_dt or not end_dt:
            return cors_response({"error": "Missing start_dt or end_dt"}, status=400)
            
        await add_block(start_dt, end_dt, reason)
        return cors_response({"status": "success"})
    except Exception as e:
        logger.exception("Error blocking time")
        return cors_response({"error": str(e)}, status=500)

async def unblock_time(request):
    """Remove blocks on a given date (YYYY-MM-DD)."""
    try:
        data = await request.json()
        date_str = data.get("date") # YYYY-MM-DD
        
        if not date_str:
            return cors_response({"error": "Missing date"}, status=400)
            
        deleted = await remove_blocks_on_date(date_str)
        return cors_response({"status": "success", "deleted_count": deleted})
    except Exception as e:
        logger.exception("Error unblocking date")
        return cors_response({"error": str(e)}, status=500)

def create_api_app():
    app = web.Application()
    app.router.add_route("OPTIONS", "/{tail:.*}", options_handler)
    app.router.add_get("/api/schedule", get_schedule)
    app.router.add_post("/api/block", block_time)
    app.router.add_post("/api/unblock", unblock_time)
    return app
