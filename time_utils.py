# time_utils.py

import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

def get_current_ist_string() -> str:
    """Generates a natural language string for the current time in IST."""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        
        # Day in Hindi
        days_hindi = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
        day_name = days_hindi[now_ist.weekday()]

        # Time of day in Hindi
        hour = now_ist.hour
        if 5 <= hour < 12:
            time_of_day = "सुबह"
        elif 12 <= hour < 17:
            time_of_day = "दोपहर"
        elif 17 <= hour < 21:
            time_of_day = "शाम"
        else:
            time_of_day = "रात"

        # Format the final string
        time_str = now_ist.strftime("%I:%M").lstrip('0') # 12-hour format without leading zero
        date_str = now_ist.strftime("%d %B %Y")
        
        return f"आज {day_name}, {date_str} है, और अभी {time_of_day} के {time_str} बजे हैं"
    except Exception as e:
        logger.error(f"Could not generate IST time string: {e}")
        return "अभी का समय और तारीख उपलब्ध नहीं है."
