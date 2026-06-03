// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    document.body.classList.add('telegram');
}

// API Server configuration (can use relative URL if served from same origin, or configured local/public URL)
const API_BASE = 'https://bot-detail.onrender.com';

let currentDate = new Date();
let selectedDate = new Date();
let scheduleData = { appointments: [], blocks: [] };

// Elements
const daysSlider = document.getElementById('days-slider');
const prevWeekBtn = document.getElementById('prev-week');
const nextWeekBtn = document.getElementById('next-week');
const todayBtn = document.getElementById('today-btn');
const slotsGrid = document.querySelector('.slots-grid');

const modal = document.getElementById('action-modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const modalActions = document.getElementById('modal-actions');
const closeBtn = document.querySelector('.close-btn');

// Start working hour / duration configuration matching config.py
const WORK_START_HOUR = 7;
const WORK_END_HOUR = 19;
const SLOT_DURATION_HOURS = 3;

// Initialize
async function init() {
    setupEventListeners();
    renderDateSlider();
    await fetchSchedule();
}

function setupEventListeners() {
    prevWeekBtn.addEventListener('click', () => navigateWeek(-7));
    nextWeekBtn.addEventListener('click', () => navigateWeek(7));
    todayBtn.addEventListener('click', () => {
        selectedDate = new Date();
        currentDate = new Date();
        renderDateSlider();
        renderScheduleGrid();
    });
    
    closeBtn.addEventListener('click', () => modal.classList.remove('open'));
    window.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('open');
    });
}

function formatDate(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

async function fetchSchedule() {
    try {
        const response = await fetch(`${API_BASE}/api/schedule`);
        if (response.ok) {
            scheduleData = await response.json();
            renderScheduleGrid();
        } else {
            console.error('Failed to fetch schedule data');
        }
    } catch (e) {
        console.error('API Error:', e);
    }
}

function navigateWeek(days) {
    currentDate.setDate(currentDate.getDate() + days);
    renderDateSlider();
}

function renderDateSlider() {
    daysSlider.innerHTML = '';
    const weekdays = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
    
    // Render 14 days around the currentDate
    const tempDate = new Date(currentDate);
    // start from current date
    for (let i = 0; i < 14; i++) {
        const cardDate = new Date(tempDate);
        const card = document.createElement('div');
        card.className = `day-card ${formatDate(cardDate) === formatDate(selectedDate) ? 'selected' : ''}`;
        
        const weekday = weekdays[cardDate.getDay()];
        const dayNum = cardDate.getDate();
        
        card.innerHTML = `
            <span class="weekday">${weekday}</span>
            <span class="day-num">${dayNum}</span>
        `;
        
        card.addEventListener('click', () => {
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedDate = cardDate;
            renderScheduleGrid();
        });
        
        daysSlider.appendChild(card);
        tempDate.setDate(tempDate.getDate() + 1);
    }
}

function renderScheduleGrid() {
    slotsGrid.innerHTML = '';
    const dateStr = formatDate(selectedDate);
    
    // Generate slots: 07:00, 10:00, 13:00, 16:00
    for (let hour = WORK_START_HOUR; hour + SLOT_DURATION_HOURS <= WORK_END_HOUR; hour += SLOT_DURATION_HOURS) {
        const row = document.createElement('div');
        row.className = 'grid-row';
        
        const timeStr = `${String(hour).padStart(2, '0')}:00`;
        const slotStartStr = `${dateStr} ${timeStr}`;
        const slotEndStr = `${dateStr} ${String(hour + SLOT_DURATION_HOURS).padStart(2, '0')}:00`;
        
        // Time cell
        const timeCell = document.createElement('div');
        timeCell.className = 'time-cell';
        timeCell.innerText = timeStr;
        row.appendChild(timeCell);
        
        // Check for blocks or appointments in this slot
        for (let line = 1; line <= 2; line++) {
            const slotCell = document.createElement('div');
            slotCell.className = 'slot-cell';
            
            // Check active blocks
            const isBlocked = scheduleData.blocks.some(b => {
                // block start < slot end AND block end > slot start
                return b.start_dt < slotEndStr && b.end_dt > slotStartStr;
            });
            
            // Check appointments for this slot and line
            const appt = scheduleData.appointments.find(a => {
                return a.line_number === line && a.start_dt < slotEndStr && a.end_dt > slotStartStr;
            });
            
            if (isBlocked) {
                const card = document.createElement('div');
                card.className = 'card blocked';
                card.innerHTML = `
                    <div class="card-title">🚨 Блокировка</div>
                    <div class="card-desc">Личные дела / выходной</div>
                `;
                card.addEventListener('click', () => showUnblockModal(dateStr));
                slotCell.appendChild(card);
            } else if (appt) {
                const isComplex = appt.service_type === 'complex';
                const card = document.createElement('div');
                card.className = `card appt ${isComplex ? 'complex' : ''}`;
                card.innerHTML = `
                    <div class="card-title">${appt.car_brand} (${appt.plate_number})</div>
                    <div class="card-desc">${isComplex ? '🧹 Химчистка' : '🚿 Мойка'}</div>
                `;
                card.addEventListener('click', () => showAppointmentModal(appt));
                slotCell.appendChild(card);
            } else {
                // Free slot
                const card = document.createElement('div');
                card.className = 'card empty';
                card.innerText = '+ Свободно';
                card.addEventListener('click', () => showBlockModal(slotStartStr, slotEndStr));
                slotCell.appendChild(card);
            }
            
            row.appendChild(slotCell);
        }
        
        slotsGrid.appendChild(row);
    }
}

function showAppointmentModal(appt) {
    modalTitle.innerText = 'Детали записи';
    const isComplex = appt.service_type === 'complex';
    
    modalBody.innerHTML = `
        <div class="info-row">
            <div class="info-label">Клиент</div>
            <div class="info-value">${appt.phone}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Автомобиль</div>
            <div class="info-value">${appt.car_brand} (${appt.car_body_name})</div>
        </div>
        <div class="info-row">
            <div class="info-label">Гос. Номер</div>
            <div class="info-value">${appt.plate_number}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Услуга</div>
            <div class="info-value">${isComplex ? '🧹 Химчистка + мойка' : '🚿 Детейлинг-мойка'}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Время</div>
            <div class="info-value">${appt.start_dt} - ${appt.end_dt}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Стоимость</div>
            <div class="info-value">${appt.price} ₽</div>
        </div>
    `;
    
    modalActions.innerHTML = ''; // Actions not needed here unless cancel appointment is handled via webapp
    modal.classList.add('open');
}

function showBlockModal(startDt, endDt) {
    modalTitle.innerText = 'Заблокировать время';
    modalBody.innerHTML = `
        <p>Вы хотите закрыть запись на этот слот?</p>
        <p style="margin-top: 8px; font-weight: 500;">Период: ${startDt} - ${endDt}</p>
    `;
    
    modalActions.innerHTML = `
        <button id="confirm-block-btn" class="btn danger">Заблокировать слот</button>
        <button id="confirm-block-day-btn" class="btn secondary">Заблокировать весь день</button>
    `;
    
    document.getElementById('confirm-block-btn').onclick = async () => {
        await executeBlock(startDt, endDt);
    };
    
    document.getElementById('confirm-block-day-btn').onclick = async () => {
        const datePart = startDt.split(' ')[0];
        const dayStart = `${datePart} 07:00`;
        const dayEnd = `${datePart} 19:00`;
        await executeBlock(dayStart, dayEnd, "Выходной");
    };
    
    modal.classList.add('open');
}

function showUnblockModal(dateStr) {
    modalTitle.innerText = 'Разблокировать день';
    modalBody.innerHTML = `
        <p>Снять все блокировки на дату <strong>${dateStr}</strong>?</p>
    `;
    
    modalActions.innerHTML = `
        <button id="confirm-unblock-btn" class="btn primary">Разблокировать день</button>
    `;
    
    document.getElementById('confirm-unblock-btn').onclick = async () => {
        await executeUnblock(dateStr);
    };
    
    modal.classList.add('open');
}

async function executeBlock(startDt, endDt, reason = "Занято") {
    try {
        const response = await fetch(`${API_BASE}/api/block`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_dt: startDt, end_dt: endDt, reason })
        });
        if (response.ok) {
            modal.classList.remove('open');
            await fetchSchedule();
            if (tg) tg.showPopup({ message: "Время заблокировано" });
        }
    } catch (e) {
        console.error(e);
    }
}

async function executeUnblock(dateStr) {
    try {
        const response = await fetch(`${API_BASE}/api/unblock`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: dateStr })
        });
        if (response.ok) {
            modal.classList.remove('open');
            await fetchSchedule();
            if (tg) tg.showPopup({ message: "Блокировка снята" });
        }
    } catch (e) {
        console.error(e);
    }
}

window.onload = init;
