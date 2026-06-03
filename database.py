import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "detailing.db"


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                telegram_id    INTEGER PRIMARY KEY,
                username       TEXT,
                phone          TEXT,
                car_brand      TEXT,
                car_body_class INTEGER,
                car_body_name  TEXT,
                plate_number   TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id    INTEGER REFERENCES clients(telegram_id),
                service_type TEXT,
                start_dt     TEXT,
                end_dt       TEXT,
                dropoff_dt   TEXT,
                line_number  INTEGER,
                price        INTEGER,
                status       TEXT DEFAULT 'new',
                reminded     INTEGER DEFAULT 0,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS blocks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                start_dt   TEXT NOT NULL,
                end_dt     TEXT NOT NULL,
                reason     TEXT DEFAULT 'Занято'
            );
        """)
        await db.commit()


# ─── Clients ───────────────────────────────────────────────────────────────

async def get_client(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def upsert_client(
    telegram_id: int,
    username: str | None,
    phone: str,
    car_brand: str,
    car_body_class: int,
    car_body_name: str,
    plate_number: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO clients
                (telegram_id, username, phone, car_brand, car_body_class, car_body_name, plate_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username       = excluded.username,
                phone          = excluded.phone,
                car_brand      = excluded.car_brand,
                car_body_class = excluded.car_body_class,
                car_body_name  = excluded.car_body_name,
                plate_number   = excluded.plate_number
        """, (telegram_id, username, phone, car_brand, car_body_class, car_body_name, plate_number))
        await db.commit()


async def get_all_clients() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM clients ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ─── Appointments ──────────────────────────────────────────────────────────

async def create_appointment(
    client_id: int,
    service_type: str,
    start_dt: str,
    end_dt: str,
    dropoff_dt: str,
    line_number: int,
    price: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO appointments
                (client_id, service_type, start_dt, end_dt, dropoff_dt, line_number, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, service_type, start_dt, end_dt, dropoff_dt, line_number, price))
        await db.commit()
        return cursor.lastrowid


async def get_client_appointments(telegram_id: int) -> list[dict]:
    """Return active appointments for a client."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM appointments
            WHERE client_id = ? AND status NOT IN ('done', 'cancelled')
            ORDER BY start_dt ASC
        """, (telegram_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_appointments_in_range(start_dt: str, end_dt: str) -> list[dict]:
    """Return all active appointments overlapping the given datetime range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM appointments
            WHERE status NOT IN ('done', 'cancelled')
              AND start_dt < ? AND end_dt > ?
            ORDER BY start_dt ASC
        """, (end_dt, start_dt)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_pending_reminders(reminder_before_dt: str, now_dt: str) -> list[dict]:
    """Return appointments that need a reminder (start_dt within window, not reminded yet)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT a.*, c.phone, c.car_brand, c.car_body_name, c.plate_number
            FROM appointments a
            JOIN clients c ON a.client_id = c.telegram_id
            WHERE a.status = 'new'
              AND a.reminded = 0
              AND a.start_dt <= ?
              AND a.start_dt > ?
        """, (reminder_before_dt, now_dt)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def mark_reminded(appointment_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET reminded = 1 WHERE id = ?",
            (appointment_id,)
        )
        await db.commit()


async def get_appointments_for_schedule(days: int = 7) -> list[dict]:
    """Return appointments for the next N days."""
    from datetime import datetime, timedelta
    now = datetime.now()
    end = now + timedelta(days=days)
    return await get_appointments_in_range(
        now.strftime("%Y-%m-%d %H:%M"),
        end.strftime("%Y-%m-%d %H:%M")
    )


# ─── Blocks ────────────────────────────────────────────────────────────────

async def add_block(start_dt: str, end_dt: str, reason: str = "Занято") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO blocks (start_dt, end_dt, reason) VALUES (?, ?, ?)",
            (start_dt, end_dt, reason)
        )
        await db.commit()


async def remove_blocks_on_date(date_str: str) -> int:
    """Remove all blocks that fall on a given date (YYYY-MM-DD). Returns count deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM blocks WHERE start_dt LIKE ?",
            (f"{date_str}%",)
        )
        await db.commit()
        return cursor.rowcount


async def get_blocks_in_range(start_dt: str, end_dt: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM blocks
            WHERE start_dt < ? AND end_dt > ?
        """, (end_dt, start_dt)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
