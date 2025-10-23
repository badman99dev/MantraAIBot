import google.generativeai as genai
import json
import logging
import os

logger = logging.getLogger(__name__)
MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

def create_quiz_data(topic: str) -> dict | None:
    """
    Generates the JSON data for a quiz question on a given topic. This tool should be called by the model to get the quiz structure. The main application will then use this data to send a native Telegram Poll.
    When the user wants to play a game, test their knowledge, or you think a quiz would be fun, call this function with a relevant topic.
    """
    logger.info(f"[QUIZ DATA GEN] Generating quiz JSON for topic: {topic}")
    
    quiz_prompt = f"""
    Create a single, interesting multiple-choice quiz question about the topic: '{topic}'.
    You MUST provide your response in a single, valid JSON object format only.
    The JSON object must have these exact keys: "question" (string), "options" (a list of exactly 4 strings), "correct_option_index" (a number from 0 to 3), and "explanation" (a short, clear string).
    
    Example for topic 'ISRO':
    {{
        "question": "ISRO ne Chandrayaan-3 ko kis launch vehicle se launch kiya tha?",
        "options": ["PSLV-C57", "GSLV MkIII (LVM3)", "SSLV-D2", "Falcon 9"],
        "correct_option_index": 1,
        "explanation": "Chandrayaan-3 ko GSLV MkIII (LVM3) se launch kiya gaya tha, jo ISRO ka sabse powerful rocket hai."
    }}
    """
    
    try:
        gemini_model = genai.GenerativeModel(MODEL_NAME)
        # Hum yahan synchronous call use kar rahe hain
        response = gemini_model.generate_content(quiz_prompt)
        
        # JSON ko saaf karna
        json_string = response.text.replace("```json", "").replace("```", "").strip()
        quiz_data = json.loads(json_string)

        # Validate karna ki saari keys maujood hain
        if not all(k in quiz_data for k in ["question", "options", "correct_option_index", "explanation"]):
            raise ValueError("Generated JSON is missing required keys.")
        if len(quiz_data["options"]) != 4:
            raise ValueError("Generated JSON does not have exactly 4 options.")

        logger.info("[QUIZ DATA GEN] Successfully generated and validated quiz JSON.")
        return quiz_data
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error creating or validating quiz JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred in create_quiz_data: {e}")
        return None
