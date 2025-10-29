# quizzes/quiz_manager.py
import os
import json
import logging
from supabase import create_client, Client
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# --- Database Connection ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = None
if url and key:
    try:
        supabase = create_client(url, key)
        logger.info("✅ Successfully connected to Supabase for quiz management.")
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Failed to create Supabase client: {e}")
else:
    logger.warning("⚠️ WARNING: SUPABASE_URL or SUPABASE_KEY not found for quiz feature.")

# This is our in-memory storage (the cache)
QUIZ_CACHE = {}

def get_quiz_set(set_id: str):
    """
    "Smart" function: first checks cache, then falls back to Supabase.
    """
    if set_id in QUIZ_CACHE and 'questions' in QUIZ_CACHE[set_id]:
        logger.info(f"✅ Found '{set_id}' with questions in cache.")
        return QUIZ_CACHE[set_id]

    if not supabase:
        return None

    logger.info(f"🟡 '{set_id}' not in cache. Searching in Supabase...")
    try:
        response = supabase.table('quizzes').select('name', 'questions').eq('set_id', set_id).single().execute()
        
        if response.data:
            logger.info(f"👍 Found '{set_id}' in Supabase. Caching it.")
            QUIZ_CACHE[set_id] = response.data
            return response.data
        else:
            logger.warning(f"❌ '{set_id}' not found in Supabase.")
            return None
    except Exception as e:
        logger.error(f"Error fetching from Supabase: {e}")
        return None

def get_all_sets():
    """
    This function gets the list of all quizzes for the start menu.
    """
    if not supabase:
        return {}
        
    try:
        response = supabase.table('quizzes').select('set_id', 'name').execute()
        if response.data:
            all_sets = {item['set_id']: {'name': item['name']} for item in response.data}
            for set_id, data in all_sets.items():
                if set_id not in QUIZ_CACHE:
                    QUIZ_CACHE[set_id] = {}
                QUIZ_CACHE[set_id]['name'] = data['name']
            return all_sets
        return {}
    except Exception as e:
        logger.error(f"Error fetching all sets from Supabase: {e}")
        return {}

def save_custom_quiz_set(context: ContextTypes.DEFAULT_TYPE, set_id: str, quiz_data: dict):
    """Saves a temporary, AI-generated quiz set to the bot's memory."""
    if 'temp_quizzes' not in context.bot_data:
        context.bot_data['temp_quizzes'] = {}
    
    # We only need the questions and a name for the session
    context.bot_data['temp_quizzes'][set_id] = {
        "name": quiz_data.get("name", "Custom Quiz"),
        "questions": quiz_data.get("questions", [])
    }
    logger.info(f"🧠 Saved temporary custom quiz '{set_id}' to bot_data.")

def get_custom_quiz_set(context: ContextTypes.DEFAULT_TYPE, set_id: str):
    """Retrieves a temporary, AI-generated quiz set from the bot's memory."""
    if 'temp_quizzes' in context.bot_data and set_id in context.bot_data['temp_quizzes']:
        logger.info(f"🧠 Retrieved temporary custom quiz '{set_id}' from bot_data.")
        return context.bot_data['temp_quizzes'][set_id]
    logger.warning(f"❌ Could not find temporary custom quiz '{set_id}' in bot_data.")
    return None
