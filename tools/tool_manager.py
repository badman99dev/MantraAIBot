# --- START OF FINAL, CORRECTED tools/tool_manager.py ---

import logging
import asyncio
import inspect
from functools import wraps
from typing import Optional

from shared_data import THREAD_LOCALS

# Apne original, simple tools ko import karo
from .youtube_tool import youtube_tool
from .quiz_tool import manage_quiz
from .movie_tools import search_movie_in_database, get_details_and_download_links

logger = logging.getLogger(__name__)

def create_tool_with_status_update(original_tool_func):
    """
    Yeh ek magic wrapper function hai.
    Yeh kisi bhi normal tool function ko leta hai aur usme 'status_update' ki
    superpower daal kar ek naya, upgraded function return karta hai.
    """
    
    @wraps(original_tool_func) # Yeh original function ka naam aur docstring copy karta hai
    def tool_wrapper(**kwargs):
        status_message = kwargs.pop('status_update', None)
        
        if status_message:
            try:
                # <<< YEH FIX KA ASLI ENGINE HAI >>>
                # Hum handlers.py se bheji gayi information ko yahan access kar rahe hain.
                bot = THREAD_LOCALS.bot
                chat_id = THREAD_LOCALS.chat_id
                loop = THREAD_LOCALS.loop
                
                async def send_update():
                    # User ko better experience dene ke liye 'typing' action bhi bhej rahe hain.
                    await bot.send_chat_action(chat_id=chat_id, action='typing')
                    await bot.send_message(chat_id=chat_id, text=status_message)

                # Message ko background (main thread) me bhejo
                future = asyncio.run_coroutine_threadsafe(send_update(), loop)
                
                # ...aur yahan confirmation ka intezaar karo.
                # Isse message hamesha tool ka kaam shuru hone se PEHLE jayega.
                future.result(timeout=5)
                logger.info(f"Status update for '{original_tool_func.__name__}' sent successfully.")
                
            except Exception as e:
                # Agar status update fail bhi ho jaaye, to bhi main tool ko chalne do.
                logger.error(f"Failed to send status_update for tool '{original_tool_func.__name__}'. ERROR: {e}", exc_info=True)
        
        # Original tool ko sirf zaroori parameters hi bhejo.
        original_params = inspect.signature(original_tool_func).parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in original_params}
        
        return original_tool_func(**filtered_kwargs)

    # Gemini ko batane ke liye ki naye function me 'status_update' parameter hai,
    # hum uski signature ko manually update karte hain.
    original_sig = inspect.signature(original_tool_func)
    new_params = list(original_sig.parameters.values())
    new_params.append(
        inspect.Parameter('status_update', 
                          inspect.Parameter.KEYWORD_ONLY, 
                          default=None, 
                          annotation=Optional[str])
    )
    
    new_sig = original_sig.replace(parameters=new_params)
    tool_wrapper.__signature__ = new_sig
    
    return tool_wrapper

# Ab hum har tool ko is magic wrapper se upgrade karke Gemini ke liye ready kar rahe hain.
AVAILABLE_TOOLS = [
    create_tool_with_status_update(youtube_tool),
    create_tool_with_status_update(manage_quiz),
    create_tool_with_status_update(search_movie_in_database),
    create_tool_with_status_update(get_details_and_download_links),
]

# --- END OF FINAL, CORRECTED tools/tool_manager.py ---
