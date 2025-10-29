# quizzes/user_quiz_data.py

"""
This module is the "Artist". It takes raw quiz result data
and formats it into the beautiful, user-facing "Detailed Review" message.
It handles all the special fonts, symbols, HTML tags, and message splitting.
"""

from html import escape

def get_question_by_id_from_data(qid, questions_data):
    """Helper to find a specific question from the question list."""
    return next((q for q in questions_data if q["id"] == qid), None)

def format_detailed_review(results: list, quiz_name: str, questions_data: list) -> list:
    """
    Takes quiz results and returns a list of formatted message strings,
    split to respect Telegram's message length limits.
    """
    message_chunks = []
    current_chunk = f"📝 ║  <b>𝐃𝐄𝐓𝐀𝐈𝐋𝐄𝐃 𝐑𝐄𝐕𝐈𝐄𝐖 » {escape(quiz_name)}</b>  ║ 📝\n\n"
    
    for i, result in enumerate(results):
        question_data = get_question_by_id_from_data(result['question_id'], questions_data)
        if not question_data:
            continue

        # Escape all user-facing text to prevent HTML errors
        escaped_question = escape(question_data['question'])
        escaped_options = [escape(opt) for opt in question_data['options']]
        
        options_text = ""
        for j, option in enumerate(escaped_options):
            label = ""
            if result.get('answered_option_id') is not None and j == result.get('answered_option_id') and j == question_data['correct_option_id']:
                label = "  ◅◅  <i>Your Answer (Correct)</i>"
            elif result.get('answered_option_id') is not None and j == result.get('answered_option_id'):
                label = "  ◅◅  <i>Your Answer</i>"
            elif j == question_data['correct_option_id']:
                label = "  ◅◅  <i>Correct Answer</i>"
            options_text += f"   ›  {option}{label}\n"

        status_map = {
            'correct': f"Sᴛᴀᴛᴜs: Cᴏʀʀᴇᴄᴛ ║ Pᴏɪɴᴛs: +{result['points_earned']} ║ Tɪᴍᴇ: {result['time_taken']:.1f}s",
            'wrong': f"Sᴛᴀᴛᴜs: Wʀᴏɴɢ ║ Pᴏɪɴᴛs: {result['points_earned']} ║ Tɪᴍᴇ: {result['time_taken']:.1f}s",
            'skipped': "Sᴛᴀᴛᴜs: Sᴋɪᴘᴘᴇᴅ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'timed_out': "Sᴛᴀᴛᴜs: Tɪᴍᴇ's Uᴘ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'stopped': "Sᴛᴀᴛᴜs: Sᴛᴏᴘᴘᴇᴅ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'postponed': "Sᴛᴀᴛᴜs: Pᴏsᴛᴘᴏɴᴇᴅ" # This is just for logic, not displayed
        }
        result_text = status_map.get(result['status'], "Sᴛᴀᴛᴜs: Uɴᴋɴᴏᴡɴ")

        # We don't need to show the full review for a postponed question
        if result['status'] == 'postponed':
            continue

        question_review = (
            "____________________________________\n\n"
            f"❰ <b>𝐐𝐮𝐞𝐬𝐭𝐢𝐨𝐧 {i+1}</b> ❱\n{escaped_question}\n\n"
            f"{options_text}\n↳  {result_text}\n\n"
        )
        
        # Split message if it gets too long for Telegram
        if len(current_chunk) + len(question_review) > 4000:
            message_chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += question_review

    # Ensure even if there are no questions reviewed, a message is sent
    if not any(r['status'] != 'postponed' for r in results):
        return [] # Return empty list if no questions were actually answered/skipped etc.

    message_chunks.append(current_chunk)
    return message_chunks
