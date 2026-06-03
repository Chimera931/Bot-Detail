"""All keyboards used in the bot."""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date, datetime, timedelta
from config import BODY_CLASSES, YANDEX_MAPS_URL, ADMIN_ID

# For local testing, webapp could run on a local tunnel (e.g. ngrok) or GitHub Pages.
# We will create an inline keyboard option specifically for Admin panel.
def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Календарь записей (Web App)", web_app={"url": "https://chimera931.github.io/Web-App-Detail/"})
    return builder.as_markup()




def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться")],
            [KeyboardButton(text="📋 Мои записи"), KeyboardButton(text="📍 Как нас найти")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def service_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚿 Детейлинг-мойка (2–3 ч)", callback_data="service:wash")
    builder.button(text="🧹 Химчистка + мойка (2 дня)", callback_data="service:complex")
    builder.adjust(1)
    return builder.as_markup()


def body_class_kb(service: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cls_id, cls in BODY_CLASSES.items():
        price_key = f"price_{service}"
        price = cls[price_key]
        label_suffix = " ₽" if cls_id == 1 else "+ ₽"
        if service == "wash":
            label = f"{cls['short']} — {price:,} ₽".replace(",", " ")
        else:
            prefix = "от " if cls_id > 1 else ""
            label = f"{cls['short']} — {prefix}{price:,} ₽".replace(",", " ")
        builder.button(text=label, callback_data=f"body:{cls_id}")
    builder.adjust(1)
    return builder.as_markup()


def use_saved_car_kb(car_brand: str, car_body_name: str, plate: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"✅ Да, {car_brand} {car_body_name} ({plate})",
        callback_data="saved_car:yes"
    )
    builder.button(text="🔄 Ввести другой автомобиль", callback_data="saved_car:no")
    builder.adjust(1)
    return builder.as_markup()


def dates_kb(dates: list[date], label_fn) -> InlineKeyboardMarkup:
    """Generic date selector. label_fn(d) -> str."""
    builder = InlineKeyboardBuilder()
    for d in dates:
        builder.button(
            text=label_fn(d),
            callback_data=f"date:{d.strftime('%Y-%m-%d')}"
        )
    builder.adjust(2)
    return builder.as_markup()


def complex_pairs_kb(pairs: list[tuple[date, date]]) -> InlineKeyboardMarkup:
    """Two-day date range selector for complex service."""
    builder = InlineKeyboardBuilder()
    MONTHS_SHORT = [
        "", "янв", "фев", "мар", "апр", "май", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек"
    ]
    for start, end in pairs:
        label = (
            f"{start.day}–{end.day} {MONTHS_SHORT[start.month]}"
            if start.month == end.month
            else f"{start.day} {MONTHS_SHORT[start.month]}–{end.day} {MONTHS_SHORT[end.month]}"
        )
        builder.button(
            text=label,
            callback_data=f"pair:{start.strftime('%Y-%m-%d')}"
        )
    builder.adjust(3)
    return builder.as_markup()


def time_slots_kb(slots: list[datetime]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in slots:
        end = s + timedelta(hours=3)
        label = f"{s.strftime('%H:%M')} – {end.strftime('%H:%M')}"
        builder.button(text=label, callback_data=f"slot:{s.strftime('%Y-%m-%d %H:%M')}")
    builder.adjust(2)
    return builder.as_markup()


def dropoff_kb(work_start_date: date) -> InlineKeyboardMarkup:
    """Choose drop-off time: evening before or morning of work_start_date."""
    builder = InlineKeyboardBuilder()
    eve = work_start_date - timedelta(days=1)
    builder.button(
        text=f"🌆 Вечером {eve.day} числа (до 20:00)",
        callback_data=f"dropoff:eve:{eve.strftime('%Y-%m-%d')} 19:00"
    )
    builder.button(
        text=f"🌅 Утром {work_start_date.day} числа (к 07:00)",
        callback_data=f"dropoff:morn:{work_start_date.strftime('%Y-%m-%d')} 07:00"
    )
    builder.adjust(1)
    return builder.as_markup()


def share_contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data="confirm:yes")
    builder.button(text="❌ Отменить", callback_data="confirm:no")
    builder.adjust(1)
    return builder.as_markup()


def navigate_kb(url: str = YANDEX_MAPS_URL) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗺️ Проложить маршрут", url=url)
    builder.adjust(1)
    return builder.as_markup()


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
