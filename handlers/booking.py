"""
Full booking flow FSM handler.
Steps: service → body class → car brand → plate → date → (slot|dropoff) → phone → confirm
"""

import logging
from datetime import datetime, timedelta, date

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import (
    ADMIN_ID, BODY_CLASSES, WORK_START_HOUR, WORK_END_HOUR,
    COMPLEX_DURATION_DAYS, BOOKING_HORIZON_DAYS,
    SERVICE_WASH, SERVICE_COMPLEX, PRICE_LABEL,
)
from database import get_client, upsert_client, create_appointment
from keyboards import (
    main_menu_kb, service_kb, body_class_kb, use_saved_car_kb,
    dates_kb, complex_pairs_kb, time_slots_kb, dropoff_kb,
    share_contact_kb, confirm_kb, navigate_kb, remove_kb,
)
from states import BookingStates
from utils import (
    get_free_wash_slots, get_free_complex_pairs, assign_line,
    build_booking_summary, build_admin_notification,
    fmt_date_ru, fmt_dt, parse_dt, fmt_price,
)

logger = logging.getLogger(__name__)
router = Router()


# ─── Entry point ───────────────────────────────────────────────────────────

@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BookingStates.choose_service)
    await message.answer(
        "Выберите услугу:",
        reply_markup=service_kb(),
    )


# ─── Step 1: Service ───────────────────────────────────────────────────────

@router.callback_query(BookingStates.choose_service, F.data.startswith("service:"))
async def cb_service(call: CallbackQuery, state: FSMContext) -> None:
    service = call.data.split(":")[1]
    await state.update_data(service=service)
    await state.set_state(BookingStates.choose_body_class)
    await call.message.edit_text(
        "Укажите класс кузова вашего автомобиля:",
        reply_markup=body_class_kb(service),
    )
    await call.answer()


# ─── Step 2: Body class ────────────────────────────────────────────────────

@router.callback_query(BookingStates.choose_body_class, F.data.startswith("body:"))
async def cb_body_class(call: CallbackQuery, state: FSMContext) -> None:
    cls_id = int(call.data.split(":")[1])
    cls_info = BODY_CLASSES[cls_id]
    data = await state.get_data()
    service = data["service"]
    price_label = fmt_price(service, cls_id)

    await state.update_data(
        car_body_class=cls_id,
        car_body_name=cls_info["short"],
        price_label=price_label,
        price_raw=cls_info[f"price_{service}"],
    )

    # Check if client has a saved car
    client = await get_client(call.from_user.id)
    if client and client.get("car_brand"):
        await state.set_state(BookingStates.enter_car_brand)
        await call.message.edit_text(
            f"💰 Стоимость для вашего класса: <b>{price_label}</b>\n\n"
            f"Хотите использовать ранее сохранённый автомобиль?",
            parse_mode="HTML",
            reply_markup=use_saved_car_kb(
                client["car_brand"],
                client["car_body_name"],
                client["plate_number"],
            ),
        )
    else:
        await state.set_state(BookingStates.enter_car_brand)
        await call.message.edit_text(
            f"💰 Стоимость для вашего класса: <b>{price_label}</b>\n\n"
            "Введите марку автомобиля (например: Toyota, BMW):",
            parse_mode="HTML",
        )
    await call.answer()


# ─── Saved car shortcut ────────────────────────────────────────────────────

@router.callback_query(BookingStates.enter_car_brand, F.data == "saved_car:yes")
async def cb_use_saved_car(call: CallbackQuery, state: FSMContext) -> None:
    client = await get_client(call.from_user.id)
    await state.update_data(
        car_brand=client["car_brand"],
        car_body_name=client["car_body_name"],
        car_body_class=client["car_body_class"],
        plate_number=client["plate_number"],
    )
    await _proceed_to_date(call.message, state, edit=True)
    await call.answer()


@router.callback_query(BookingStates.enter_car_brand, F.data == "saved_car:no")
async def cb_enter_new_car(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text("Введите марку автомобиля (например: Toyota, BMW):")
    await call.answer()


# ─── Step 3: Car brand (text) ──────────────────────────────────────────────

@router.message(BookingStates.enter_car_brand)
async def msg_car_brand(message: Message, state: FSMContext) -> None:
    brand = message.text.strip()
    if len(brand) < 2:
        await message.answer("Пожалуйста, введите корректное название марки.")
        return
    await state.update_data(car_brand=brand)
    await state.set_state(BookingStates.enter_plate_number)
    await message.answer("Введите государственный номер автомобиля (например: А123АА777):")


# ─── Step 4: Plate number (text) ───────────────────────────────────────────

@router.message(BookingStates.enter_plate_number)
async def msg_plate_number(message: Message, state: FSMContext) -> None:
    plate = message.text.strip().upper()
    if len(plate) < 4:
        await message.answer("Пожалуйста, введите корректный гос. номер.")
        return
    await state.update_data(plate_number=plate)
    await _proceed_to_date(message, state, edit=False)


# ─── Step 5: Date selection ────────────────────────────────────────────────

async def _proceed_to_date(msg_or_cb, state: FSMContext, edit: bool = False) -> None:
    data = await state.get_data()
    service = data["service"]

    if service == SERVICE_WASH:
        await state.set_state(BookingStates.choose_date)
        today = date.today()
        available_days: list[date] = []
        for offset in range(1, BOOKING_HORIZON_DAYS + 1):
            d = today + timedelta(days=offset)
            slots = await get_free_wash_slots(d)
            if slots:
                available_days.append(d)

        if not available_days:
            text = "😔 К сожалению, свободных слотов нет на ближайшие 30 дней. Попробуйте позже."
            if edit:
                await msg_or_cb.edit_text(text)
            else:
                await msg_or_cb.answer(text)
            await state.clear()
            return

        def label(d: date) -> str:
            return fmt_date_ru(d)

        text = "📅 Выберите удобную дату для мойки:"
        kb = dates_kb(available_days, label)
        if edit:
            await msg_or_cb.edit_text(text, reply_markup=kb)
        else:
            await msg_or_cb.answer(text, reply_markup=kb)

    else:  # complex
        await state.set_state(BookingStates.choose_date)
        today = date.today()
        pairs = await get_free_complex_pairs(today + timedelta(days=1))

        if not pairs:
            text = "😔 Нет свободных окон для химчистки на ближайшие 30 дней. Попробуйте позже."
            if edit:
                await msg_or_cb.edit_text(text)
            else:
                await msg_or_cb.answer(text)
            await state.clear()
            return

        text = (
            "📅 Химчистка занимает <b>2 рабочих дня</b>.\n"
            "Выберите удобный период:"
        )
        kb = complex_pairs_kb(pairs)
        if edit:
            await msg_or_cb.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await msg_or_cb.answer(text, parse_mode="HTML", reply_markup=kb)


# ─── Date chosen ───────────────────────────────────────────────────────────

@router.callback_query(BookingStates.choose_date, F.data.startswith("date:"))
async def cb_date_wash(call: CallbackQuery, state: FSMContext) -> None:
    date_str = call.data.split(":")[1]
    chosen_date = date.fromisoformat(date_str)
    slots = await get_free_wash_slots(chosen_date)

    if not slots:
        await call.answer("Все слоты на этот день заняты, выберите другой.", show_alert=True)
        return

    await state.update_data(chosen_date=date_str)
    await state.set_state(BookingStates.choose_slot)
    await call.message.edit_text(
        f"📅 {fmt_date_ru(chosen_date)}\nВыберите удобное время:",
        reply_markup=time_slots_kb(slots),
    )
    await call.answer()


@router.callback_query(BookingStates.choose_date, F.data.startswith("pair:"))
async def cb_date_complex(call: CallbackQuery, state: FSMContext) -> None:
    start_str = call.data.split(":")[1]
    work_start = date.fromisoformat(start_str)
    work_end = work_start + timedelta(days=COMPLEX_DURATION_DAYS)

    await state.update_data(
        chosen_date=start_str,
        work_start=start_str,
        work_end=work_end.strftime("%Y-%m-%d"),
        date_label=(
            f"{fmt_date_ru(work_start)} — {fmt_date_ru(work_end - timedelta(days=1))}"
        ),
    )
    await state.set_state(BookingStates.choose_dropoff)
    await call.message.edit_text(
        f"📅 Выбран период: <b>{fmt_date_ru(work_start)} — {fmt_date_ru(work_end - timedelta(days=1))}</b>\n\n"
        "Когда удобнее пригнать автомобиль?",
        parse_mode="HTML",
        reply_markup=dropoff_kb(work_start),
    )
    await call.answer()


# ─── Step 5b: Wash time slot ──────────────────────────────────────────────

@router.callback_query(BookingStates.choose_slot, F.data.startswith("slot:"))
async def cb_slot(call: CallbackQuery, state: FSMContext) -> None:
    slot_str = call.data.split("slot:")[1]
    slot_start = datetime.strptime(slot_str, "%Y-%m-%d %H:%M")
    slot_end = slot_start + timedelta(hours=3)
    await state.update_data(
        start_dt=fmt_dt(slot_start),
        end_dt=fmt_dt(slot_end),
        dropoff_dt=fmt_dt(slot_start),
        date_label=f"{fmt_date_ru(slot_start)} {slot_start.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}",
    )
    await _proceed_to_phone(call.message, state, edit=True)
    await call.answer()


# ─── Step 5c: Complex drop-off time ───────────────────────────────────────

@router.callback_query(BookingStates.choose_dropoff, F.data.startswith("dropoff:"))
async def cb_dropoff(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    # dropoff:eve:2026-06-14 19:00  or  dropoff:morn:2026-06-15 07:00
    dropoff_dt_str = ":".join(parts[2:])
    data = await state.get_data()
    work_start_date = date.fromisoformat(data["work_start"])
    work_end_date = date.fromisoformat(data["work_end"])
    start_dt = datetime(work_start_date.year, work_start_date.month, work_start_date.day, WORK_START_HOUR, 0)
    end_dt = datetime(work_end_date.year, work_end_date.month, work_end_date.day, WORK_END_HOUR, 0)

    await state.update_data(
        start_dt=fmt_dt(start_dt),
        end_dt=fmt_dt(end_dt),
        dropoff_dt=dropoff_dt_str,
    )
    await _proceed_to_phone(call.message, state, edit=True)
    await call.answer()


# ─── Step 6: Phone ─────────────────────────────────────────────────────────

async def _proceed_to_phone(message: Message, state: FSMContext, edit: bool = False) -> None:
    await state.set_state(BookingStates.share_contact)
    text = "📱 Нажмите кнопку ниже, чтобы поделиться номером телефона для подтверждения записи:"
    if edit:
        await message.edit_text(text)
        await message.answer(text, reply_markup=share_contact_kb())
    else:
        await message.answer(text, reply_markup=share_contact_kb())


@router.message(BookingStates.share_contact, F.contact)
async def msg_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone=phone)
    data = await state.get_data()
    summary = build_booking_summary(data)
    await state.set_state(BookingStates.confirm)
    await message.answer(
        f"{summary}\nВсё верно? Подтвердите запись:",
        parse_mode="HTML",
        reply_markup=confirm_kb(),
    )


@router.message(BookingStates.share_contact)
async def msg_no_contact(message: Message) -> None:
    await message.answer(
        "Пожалуйста, воспользуйтесь кнопкой «Поделиться номером телефона» ниже.",
        reply_markup=share_contact_kb(),
    )


# ─── Step 7: Confirm ───────────────────────────────────────────────────────

@router.callback_query(BookingStates.confirm, F.data == "confirm:yes")
async def cb_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    slot_start = parse_dt(data["start_dt"])
    slot_end = parse_dt(data["end_dt"])

    line = await assign_line(slot_start, slot_end, data["service"])
    if line is None:
        await call.message.edit_text(
            "😔 К сожалению, это время только что заняли. Пожалуйста, начните запись заново и выберите другое время.",
        )
        await state.clear()
        await call.answer()
        return

    # Save / update client
    await upsert_client(
        telegram_id=call.from_user.id,
        username=call.from_user.username,
        phone=data["phone"],
        car_brand=data["car_brand"],
        car_body_class=data["car_body_class"],
        car_body_name=data["car_body_name"],
        plate_number=data["plate_number"],
    )

    # Save appointment
    await create_appointment(
        client_id=call.from_user.id,
        service_type=data["service"],
        start_dt=data["start_dt"],
        end_dt=data["end_dt"],
        dropoff_dt=data.get("dropoff_dt", data["start_dt"]),
        line_number=line,
        price=data["price_raw"],
    )

    client = await get_client(call.from_user.id)

    # Notify client
    await call.message.edit_text(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"{build_booking_summary(data)}\n"
        f"Ждём вас! Если нужно отменить — позвоните нам 📞",
        parse_mode="HTML",
    )
    await call.message.answer(
        "📍 Как добраться до нас:",
        reply_markup=navigate_kb(),
    )
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())

    # Notify admin
    admin_text = build_admin_notification(data, client, line)
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

    await state.clear()
    await call.answer()


@router.callback_query(BookingStates.confirm, F.data == "confirm:no")
async def cb_cancel_booking(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Запись отменена. Возвращайтесь, когда будете готовы! 👋")
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()
