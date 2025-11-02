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

# --- NEW: DYNAMIC API KEY & MODEL POPOOL SETUP (WITH FULL DEBUGGING) ---

# +++ START OF DEBUG BLOCK +++
print("\n" + "="*50)
print(" S T A R T I N G   A P I   K E Y   D E B U G G I N G ")
print("="*50 + "\n")

# 1. Check TOTAL_GEMINI_KEYS
total_keys_str = os.environ.get("TOTAL_GEMINI_KEYS")
print(f"DEBUG STEP 1: Reading 'TOTAL_GEMINI_KEYS'. Found value: '{total_keys_str}' (Type: {type(total_keys_str)})")
# +++ END OF DEBUG BLOCK +++

try:
    TOTAL_KEYS = int(total_keys_str or 0)
    if TOTAL_KEYS == 0:
        logger.warning("TOTAL_GEMINI_KEYS environment variable not set or is 0. Will check for fallback keys.")
except ValueError:
    raise ValueError(f"CRITICAL ERROR: TOTAL_GEMINI_KEYS must be a valid number, but got '{total_keys_str}'.")

API_KEYS = []
if TOTAL_KEYS > 0:
    print(f"\nDEBUG STEP 2: Looping from 1 to {TOTAL_KEYS} to find GEMINI_KEY_n variables...")
    for i in range(1, TOTAL_KEYS + 1):
        key_name = f"GEMINI_KEY_{i}"
        key_value = os.environ.get(key_name)
        # We print the name and whether it was found, but not the key itself for security.
        print(f"  - Checking for '{key_name}': {'FOUND' if key_value else '!!! NOT FOUND !!!'}")
        if key_value:
            API_KEYS.append(key_value)
        else:
            logger.warning(f"Configuration warning: TOTAL_GEMINI_KEYS is {TOTAL_KEYS}, but '{key_name}' is missing.")
else:
    print("\nDEBUG STEP 2: TOTAL_GEMINI_KEYS is 0. Checking for fallback keys (GEMINI_KEYS or GEMINI_KEY)...")
    # Fallback for old comma-separated key system
    fallback_keys_str = os.environ.get("GEMINI_KEYS")
    if fallback_keys_str:
        print(f"  - Found fallback 'GEMINI_KEYS': '{fallback_keys_str}'")
        API_KEYS = [key.strip() for key in fallback_keys_str.split(',')]
    else:
        # Fallback for single key system
        fallback_single_key = os.environ.get("GEMINI_KEY")
        if fallback_single_key:
            print(f"  - Found fallback 'GEMINI_KEY': '...{fallback_single_key[-4:]}'")
            API_KEYS.append(fallback_single_key)
        else:
            print("  - No fallback keys found.")

# +++ START OF FINAL DEBUG CHECK +++
print("\nDEBUG STEP 3: Final check of the API_KEYS list.")
print(f"  - Total keys collected: {len(API_KEYS)}")
if API_KEYS:
    print("  - Status: Keys were successfully loaded.")
else:
    print("  - CRITICAL STATUS: The API_KEYS list is EMPTY. This will cause the bot to fail.")
print("\n" + "="*50)
print(" D E B U G G I N G   C O M P L E T E D ")
print("="*50 + "\n")
# +++ END OF FINAL DEBUG CHECK +++


if not API_KEYS:
    # This will now definitely catch the error if no keys are found
    raise ValueError("FATAL ERROR: No Gemini API keys were found after checking all environment variables. The bot cannot start. Please check your Render environment settings.")

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

MODEL_POOL = []
for key in API_KEYS:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name=MODEL_NAME, tools=AVAILABLE_TOOLS)
    MODEL_POOL.append(model)
    logger.info(f"Successfully initialized a model instance for key ending with '...{key[-4:]}'")

current_model_index = 0
model_lock = threading.Lock()

def get_next_model() -> genai.GenerativeModel:
    """Safely gets the next model from the pool in a round-robin fashion."""
    global current_model_index
    with model_lock:
        # Extra safety check, though the startup check should prevent this
        if not MODEL_POOL:
            logger.critical("FATAL: get_next_model was called but MODEL_POOL is empty!")
            return None
        model = MODEL_POOL[current_model_index]
        current_model_index = (current_model_index + 1) % len(MODEL_POOL)
        return model

# --- CHAT SESSION & HISTORY MANAGEMENT ---
# (The rest of this file remains exactly the same)
user_chats = {} 
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

async def manage_chat_history(chat_session: genai.ChatSession):
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
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id}...")
        selected_model = get_next_model()
        
        # This is where the original error happened. Now 'selected_model' cannot be None.
        if selected_model is None:
            # This is a fallback error in case the startup check somehow fails
            raise RuntimeError("Could not retrieve a valid model from the pool. Check startup logs for key errors.")
            
        logger.info(f"Assigned model with key '...{selected_model._client._api_key[-4:]}' to user {user_id}")
        
        personalization_section = ""
        if user_id in settings.user_profiles and settings.user_profiles[user_id]:
            profile = settings.user_profiles[user_id]
            personalization_section += "\n--- USER'S PERSONAL DATA (Remember This!) ---\n"
            # ... (rest of personalization) ...
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
