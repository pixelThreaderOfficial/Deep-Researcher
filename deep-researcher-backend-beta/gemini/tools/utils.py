from datetime import datetime

def get_current_time() -> str:
    """Returns the current time as a natural phrase"""
    time = datetime.now().strftime("%I:%M %p").lstrip("0")
    return f"It is {time} right now."

def get_current_date() -> str:
    """Returns the current date as a natural phrase"""
    date = datetime.now().strftime("%B %d, %Y")
    return f"Today's date is {date}."

def current_day() -> str:
    """Returns the current day as a natural phrase"""
    day = datetime.now().strftime("%A")
    return f"Today is {day}."
