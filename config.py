# config.py

import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. SETUP ---
load_dotenv()

# --- Environment Variables ---
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ.get('GEMINI_KEY')
if not GEMINI_KEY:
    raise ValueError("GEMINI_KEY not found in .env file. Please add it.")

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Gemini AI Configuration ---
genai.configure(api_key=GEMINI_KEY)

# --- History Management Constants ---
MAX_HISTORY_TOKENS = 50000
TRIM_BUFFER_TOKENS = 5000
