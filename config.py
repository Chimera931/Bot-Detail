import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot ───────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
ADMIN_PHONE: str = os.getenv("ADMIN_PHONE", "+7XXXXXXXXXX")
YANDEX_MAPS_URL: str = os.getenv(
    "YANDEX_MAPS_URL",
    "https://yandex.ru/maps/"
)

# ─── Schedule ──────────────────────────────────────────────────────────────
WORK_START_HOUR: int = 7       # 07:00
WORK_END_HOUR: int = 19        # до 19:00
SLOT_DURATION_HOURS: int = 3   # длительность одного слота мойки (часы)
COMPLEX_DURATION_DAYS: int = 2 # длительность химчистки (дни)
BOOKING_HORIZON_DAYS: int = 30 # на сколько дней вперёд открыта запись

# ─── Lines ─────────────────────────────────────────────────────────────────
MAX_LINES: int = 2  # Линия 1 — любые услуги, Линия 2 — только мойки

# ─── Services ──────────────────────────────────────────────────────────────
SERVICE_WASH = "wash"
SERVICE_COMPLEX = "complex"

SERVICE_NAMES = {
    SERVICE_WASH: "🚿 Детейлинг-мойка",
    SERVICE_COMPLEX: "🧹 Химчистка + мойка",
}

# ─── Car body classes ──────────────────────────────────────────────────────
BODY_CLASSES = {
    1: {
        "name": "Купе / Хэтчбек / Седан / Лифтбек",
        "short": "Класс I (Хэтчбек/Седан)",
        "price_wash": 3_000,
        "price_complex": 12_000,
    },
    2: {
        "name": "Кроссовер / Паркетник / Универсал",
        "short": "Класс II (Кроссовер)",
        "price_wash": 4_000,
        "price_complex": 15_000,   # показываем «от 15 000»
    },
    3: {
        "name": "Большой внедорожник / Минивэн / Пикап",
        "short": "Класс III (Внедорожник/Минивэн)",
        "price_wash": 5_000,
        "price_complex": 18_000,   # показываем «от 18 000»
    },
}

PRICE_LABEL = {
    (SERVICE_WASH, 1): "3 000 ₽",
    (SERVICE_WASH, 2): "4 000 ₽",
    (SERVICE_WASH, 3): "5 000 ₽",
    (SERVICE_COMPLEX, 1): "12 000 ₽",
    (SERVICE_COMPLEX, 2): "от 15 000 ₽",
    (SERVICE_COMPLEX, 3): "от 18 000 ₽",
}

# ─── Appointment statuses ──────────────────────────────────────────────────
STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"
