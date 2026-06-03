from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """FSM states for the booking flow."""

    # Step 1: service type
    choose_service = State()

    # Step 2: car body class
    choose_body_class = State()

    # Step 3: car brand (text input)
    enter_car_brand = State()

    # Step 4: plate number (text input)
    enter_plate_number = State()

    # Step 5a: choose date
    choose_date = State()

    # Step 5b: choose time slot (wash only)
    choose_slot = State()

    # Step 5c: choose drop-off time (complex only)
    choose_dropoff = State()

    # Step 6: share phone contact
    share_contact = State()

    # Step 7: confirm booking
    confirm = State()


