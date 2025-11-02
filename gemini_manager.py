# gemini_manager.py
import os
import logging
import threading
import google.generativeai as genai

from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
import settings
import config

logger = logging.getLogger(__name__)

# --- NEW: DYNAMIC API KEY & MODEL POOL SETUP ---
try:
    TOTAL_KEYS = int(os.environ.get("TOTAL_GEMINI_KEYS", 0))
    if TOTAL_KEYS == 0:
        logger.warning("TOTAL_GEMINI_KEYS environment variable not set or is 0. Attempting to find keys manually.")
except ValueError:
    raise ValueError("TOTAL_GEMINI_KEYS must be a valid number.")

API_KEYS = []
if TOTAL_KEYS > 0:
    for i in range(1, TOTAL_KEYS + 1):
        key = os.environ.get(f"GEMINI_KEY_{i}")
        if key:
            API_KEYS.append(key)
        else:
            logger.warning(f"Found TOTAL_GEMINI_KEYS={TOTAL_KEYS}, but GEMINI_KEY_{i} is missing.")
else:
    # Fallback for old single key system, makes it backward compatible
    single_key = os.environ.get("GEMINI_KEYS") or os.environ.get("GEMINI_KEY")
    if single_key:
        API_KEYS.append(single_key)

if not API_KEYS:
    raise ValueError("No Gemini API keys were found. Please set TOTAL_GEMINI_KEYS and GEMINI_KEY_n variables.")

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

MODEL_POOL = []
for key in API_KEYS:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name=MODEL_NAME, tools=AVAILABLE_TOOLS)
    MODEL_POOL.append(model)
    logger.info(f"Initialized a model instance for key ending with '...{key[-4:]}'")

current_model_index = 0
model_lock = threading.Lock()

def get_next_model() -> genai.GenerativeModel:
    """Safely gets the next model from the pool in a round-robin fashion."""
    global current_model_index
    with model_lock:
        model = MODEL_POOL[current_model_index]
        current_model_index = (current_model_index + 1) % len(MODEL_POOL)
        return model

# --- CHAT SESSION & HISTORY MANAGEMENT ---
# (The rest of this file remains exactly the same as before)
user_chats = {} 
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

async def manage_chat_history(chat_session: genai.ChatSession):
    """Checks the chat history's token count and trims it if it exceeds the limit."""
    try:
        model = chat_session.model
        token_count = (await model.count_tokens_async(chat_session.history)).total_tokens
        
        if token_count > config.MAX_HISTORY_TOKENS:
            logger.warning(f"Token count {token_count} is over the limit. Trimming.")
            
            current_history = chat_session.history
            safe_limit = config.MAX_HISTORY_TOKENS - config.TRIM_BUFFER_TOKENS
            
            while (await model.count_tokens_async(current_history)).total_tokens > safe_limit:
                if len(current_history) > 3:
                    del current_history[2]; del current_history[2]
                else:
                    break
                    
            chat_session.history = current_history
            new_count = (await model.count_tokens_async(chat_session.history)).total_tokens
            logger.info(f"History trimmed. New token count is {new_count}")
    except Exception as e:
        logger.error(f"Error during chat history management: {e}", exc_info=True)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    """Gets an existing chat session or creates a new one with a model from the pool."""
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id}...")
        selected_model = get_next_model()
        logger.info(f"Assigned model with key '...{selected_model._client._api_key[-4:]}' to user {user_id}")
        
        personalization_section = ""
        if user_id in settings.user_profiles and settings.user_profiles[user_id]:
            profile = settings.user_profiles[user_id]
            personalization_section += "\n--- USER'S PERSONAL DATA (Remember This!) ---\n"
            if 'nickname' in profile: personalization_section += f"- User's Nickname: {profile['nickname']}\n"
            if 'instruction' in profile: personalization_section += f"- Custom Instruction: {profile['instruction']}\n"
            if 'hobby' in profile: personalization_section += f"- User's Hobby: {profile['hobby']}\n"
            if 'memory' in profile: personalization_section += f"- Important Memory: {profile['memory']}\n"
            
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            user_name=user_name,
            user_personalization_section=personalization_section
        )
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = selected_model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]
