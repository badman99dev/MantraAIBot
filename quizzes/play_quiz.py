# --- START OF UPDATED FILE quizzes/play_quiz.py ---

import asyncio
import time
import os
import json
import random
import logging
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# === MODIFIED IMPORTS ===
# In functions se humein quiz data aur AI chat session milega
from .user_quiz_data import get_question_by_id_from_data
from ai_manager import user_chats 
from response_filter import sanitize_html

logger = logging.getLogger(__name__)

# --- Constants ---
SECONDS_PER_QUESTION = 30
POINTS_CORRECT = 100
POINTS_WRONG_PENALTY = -25
MAX_SPEED_BONUS = 50
CONSECUTIVE_TIMEOUT_LIMIT = 5
RESULTS_DIR = "quiz_results"


# ================================================================================= #
# ===> START: NAYA "PRO MOVE" LOGIC (LIVE CONTEXT INJECTION) <===
# ================================================================================= #

def _generate_live_quiz_report(session: 'QuizSession') -> str:
    """AI ke context ke liye ek live report string banata hai."""
    if not hasattr(session, 'questions_data'): return ""

    report_lines = [
        "--- 🔴 LIVE QUIZ REPORT (For AI's Eyes Only. Do not show this block to the user.) ---",
        f"Quiz Name: {escape(session.quiz_name)}",
        f"Current Score: {session.total_score}",
        "Status:",
    ]
    
    for result in session.results:
        q_data = get_question_by_id_from_data(result['question_id'], session.questions_data)
        if not q_data: continue
        
        status_icon = "✅" if result['status'] == 'correct' else ("❌" if result['status'] in ['wrong', 'timed_out', 'skipped'] else "⏹️")
        user_answer_text = f"(User chose: '{escape(q_data['options'][result['answered_option_id']])}')" if result.get('answered_option_id') is not None else "(User did not answer)"
        correct_answer_text = f"(Correct: '{escape(q_data['options'][q_data['correct_option_id']])}')"
        
        report_lines.append(
            f"  {status_icon} Q: {escape(q_data['question'])} {user_answer_text} {correct_answer_text}"
        )

    if session.questions_queue and not session.is_suspended:
        current_q_id = session.questions_queue[0]
        q_data = get_question_by_id_from_data(current_q_id, session.questions_data)
        if q_data:
            report_lines.append(
                f"  ⏳ CURRENT Q: {escape(q_data['question'])} (Waiting for user's answer...)"
            )

    report_lines.append("--- END OF REPORT ---")
    return "\n".join(report_lines)


async def _update_ai_context_with_quiz_state(user_id: int, session: 'QuizSession'):
    """User ko message bheje bina AI ke chat history ko silently update karta hai."""
    try:
        if user_id not in user_chats: return

        chat_session = user_chats[user_id]
        live_report = _generate_live_quiz_report(session)
        if not live_report: return

        # History ko ulta check karo taaki last report jaldi mil jaye
        for i in range(len(chat_session.history) - 1, -1, -1):
            if chat_session.history[i].role == 'model':
                if "--- 🔴 LIVE QUIZ REPORT" in chat_session.history[i].parts[0].text:
                    chat_session.history[i].parts[0].text = live_report
                    logger.info(f"Updated live quiz context for user {user_id}")
                    return

        # Agar pichli report nahi mili (quiz ka pehla update hai)
        from google.generativeai.types import content_types
        new_content = content_types.to_content({'role': 'model', 'parts': [{'text': live_report}]})
        chat_session.history.append(new_content)
        logger.info(f"Injected initial live quiz context for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to update AI context for user {user_id}: {e}", exc_info=True)


async def _remove_ai_quiz_context(user_id: int):
    """Quiz khatm hone par AI ki history se live report ko saaf karta hai."""
    try:
        if user_id not in user_chats: return
        chat_session = user_chats[user_id]
        
        for i in range(len(chat_session.history) - 1, -1, -1):
            if chat_session.history[i].role == 'model' and "--- 🔴 LIVE QUIZ REPORT" in chat_session.history[i].parts[0].text:
                del chat_session.history[i]
                logger.info(f"Cleaned up quiz context for user {user_id}")
                return
    except Exception as e:
        logger.error(f"Failed to clean up AI context for user {user_id}: {e}", exc_info=True)


# ================================================================================= #
# ===> END: NAYA "PRO MOVE" LOGIC <===
# ================================================================================= #


# --- The Game Session Class ---
class QuizSession:
    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, set_id: str, quiz_data: dict, is_temp_quiz: bool = False):
        self.context = context
        self.chat_id = chat_id
        self.set_id = set_id
        self.quiz_name = quiz_data.get('name', 'Custom Quiz')
        self.questions_data = list(quiz_data.get('questions', []))
        random.shuffle(self.questions_data)
        self.questions_queue = [q['id'] for q in self.questions_data]
        self.results = []
        self.total_score = 0
        self.active_poll_message_id = None
        self.active_poll_id = None
        self.session_id = f"{chat_id}_{int(time.time())}"
        self.consecutive_timeouts = 0
        self.is_suspended = False
        self.is_temp_quiz = is_temp_quiz

    async def start(self):
        try:
            msg = await self.context.bot.send_message(self.chat_id, text="Get Ready... 3️⃣")
            await asyncio.sleep(1.0); await msg.edit_text("Get Ready... 2️⃣")
            await asyncio.sleep(1.0); await msg.edit_text("Get Ready... 1️⃣")
            await asyncio.sleep(1.0); await msg.edit_text("🚦 GO!")
            await asyncio.sleep(0.5); await msg.delete()
        except BadRequest as e:
            logger.warning(f"Countdown message error for chat {self.chat_id}: {e}")
        await self.send_next_question()

    async def send_next_question(self):
        delete_task = None
        if self.active_poll_message_id:
            delete_task = self.context.bot.delete_message(self.chat_id, self.active_poll_message_id)
        
        if not self.questions_queue:
            if delete_task:
                try: await delete_task
                except BadRequest: pass
            await self.show_final_score()
            return
        
        # === NAYA CODE ===
        # Pehle question par context inject karo
        if len(self.results) == 0:
            asyncio.create_task(_update_ai_context_with_quiz_state(self.chat_id, self))

        question_id = self.questions_queue[0]
        question_data = get_question_by_id_from_data(question_id, self.questions_data)
        question_timer = question_data.get('timer_seconds', SECONDS_PER_QUESTION)
        total_answered = len(self.results)
        is_postponed = getattr(self, f"is_postponed_{question_id}", False)
        
        keyboard = [[InlineKeyboardButton("⏹️ Stop Quiz", callback_data=f'quizgame_stop_quiz')]]
        if is_postponed:
            keyboard[0].append(InlineKeyboardButton("⏩ Skip Permanently", callback_data=f'quizgame_skip_permanently'))
        else:
            keyboard[0].append(InlineKeyboardButton("➡️ Postpone", callback_data=f'quizgame_postpone_question'))

        send_task = self.context.bot.send_poll(
            chat_id=self.chat_id, question=f"Q {total_answered + 1}/{len(self.questions_data)}: {question_data['question']}",
            options=question_data["options"], type='quiz', correct_option_id=question_data["correct_option_id"],
            open_period=question_timer, is_anonymous=False, reply_markup=InlineKeyboardMarkup(keyboard)
        )
        try:
            if delete_task: _, message = await asyncio.gather(delete_task, send_task)
            else: message = await send_task
        except BadRequest as e:
            logger.error(f"Failed to send next question for chat {self.chat_id}: {e}")
            return

        self.active_poll_message_id = message.message_id
        self.active_poll_id = message.poll.id
        self.context.bot_data[self.active_poll_id] = {"session": self, "question_id": question_id, "time_sent": time.time()}
        
        self.context.job_queue.run_once(self.handle_timeout_job, question_timer + 1.5, data={'poll_id': self.active_poll_id}, name=f"timeout_{self.active_poll_id}")

    async def handle_answer(self, update: Update):
        poll_id = self.active_poll_id
        jobs = self.context.job_queue.get_jobs_by_name(f"timeout_{poll_id}")
        for job in jobs: job.schedule_removal()
        quiz_info = self.context.bot_data.pop(poll_id, None)
        if not quiz_info or not self.questions_queue or self.is_suspended: return
        self.consecutive_timeouts = 0
        answer = update.poll_answer
        time_taken = time.time() - quiz_info['time_sent']
        question_id = self.questions_queue.pop(0)
        question_data = get_question_by_id_from_data(question_id, self.questions_data)
        question_timer = question_data.get('timer_seconds', SECONDS_PER_QUESTION)
        is_correct = answer.option_ids[0] == question_data["correct_option_id"]
        points, status = (POINTS_CORRECT + calculate_points(time_taken, question_timer), 'correct') if is_correct else (POINTS_WRONG_PENALTY, 'wrong')
        
        self.total_score += points
        self.results.append({'question_id': question_id, 'status': status, 'points_earned': points, 'time_taken': time_taken, 'answered_option_id': answer.option_ids[0]})
        
        # === NAYA CODE ===
        # Har answer ke baad context update karo
        asyncio.create_task(_update_ai_context_with_quiz_state(update.poll_answer.user.id, self))

        await asyncio.sleep(0.7)
        await self.send_next_question()

    async def handle_timeout_job(self, context: ContextTypes.DEFAULT_TYPE):
        poll_id = context.job.data['poll_id']
        if poll_id in self.context.bot_data:
            self.consecutive_timeouts += 1
            if self.consecutive_timeouts >= CONSECUTIVE_TIMEOUT_LIMIT:
                await self.suspend_quiz(); return
            await self.handle_closure(poll_id=poll_id)
            
    async def handle_closure(self, poll_id: str, stopped=False, postponed=False, skipped=False):
        quiz_info = self.context.bot_data.pop(poll_id, None)
        if not quiz_info or not self.questions_queue or self.is_suspended: return
        if quiz_info.get("question_id") == self.questions_queue[0]:
            question_id = self.questions_queue.pop(0)
            question_data = get_question_by_id_from_data(question_id, self.questions_data)
            question_timer = question_data.get('timer_seconds', SECONDS_PER_QUESTION)
            status = 'timed_out'
            if postponed:
                self.questions_queue.append(question_id)
                setattr(self, f"is_postponed_{question_id}", True); status = 'postponed'
            elif skipped: status = 'skipped'
            elif stopped: status = 'stopped'
            self.results.append({'question_id': question_id, 'status': status, 'points_earned': 0, 'time_taken': question_timer, 'answered_option_id': None})
            
            # === NAYA CODE ===
            # Timeout/Skip/Stop par context update karo
            asyncio.create_task(_update_ai_context_with_quiz_state(self.chat_id, self))

            if not self.questions_queue or stopped:
                await self.show_final_score()
            else:
                await self.send_next_question()

    async def suspend_quiz(self):
        if self.is_suspended: return
        self.is_suspended = True
        if self.active_poll_id in self.context.bot_data: self.context.bot_data.pop(self.active_poll_id)
        jobs = self.context.job_queue.get_jobs_by_name(f"timeout_{self.active_poll_id}")
        for job in jobs: job.schedule_removal()
        try:
            await self.context.bot.delete_message(self.chat_id, self.active_poll_message_id)
        except BadRequest: pass
        logger.warning(f"Quiz suspended for chat {self.chat_id} due to inactivity.")
        keyboard = [[InlineKeyboardButton("🔄      Try Again      🔄", callback_data=f'quizgame_try_again:{self.set_id}')]]
        await self.context.bot.send_message(self.chat_id, text="⚠️ Quiz session has been suspended due to inactivity.", reply_markup=InlineKeyboardMarkup(keyboard))
        
        # === NAYA CODE ===
        # Inactivity par context clean karo
        asyncio.create_task(_remove_ai_quiz_context(self.chat_id))

    async def show_final_score(self):
        if self.is_suspended: return
        self.is_suspended = True

        correct_count = sum(1 for r in self.results if r['status'] == 'correct')
        wrong_count = sum(1 for r in self.results if r['status'] == 'wrong')
        score_text = (f"⫷ 🏆 <b>𝐅𝐈𝐍𝐀𝐋 𝐒𝐂𝐎𝐑𝐄 » {escape(self.quiz_name)}</b> 🏆 ⫸\n\n"
                      f"    ✅ Correct       »  <code>{correct_count}</code>\n"
                      f"    ❌ Wrong         »  <code>{wrong_count}</code>\n\n"
                      f"    ✪ <b>Total Points</b>  »  <code>{self.total_score}</code>")
        
        if not os.path.exists(RESULTS_DIR): os.makedirs(RESULTS_DIR)
        data_to_save = {'results': self.results, 'quiz_name': self.quiz_name, 'questions_data': self.questions_data}
        with open(f"{RESULTS_DIR}/{self.session_id}.json", "w") as f: json.dump(data_to_save, f, indent=2)

        keyboard = [
            [InlineKeyboardButton("📊 Detailed Review", callback_data=f'quizgame_detailed_review:{self.session_id}')]
        ]
        if self.is_temp_quiz:
            keyboard.append([InlineKeyboardButton("🔄      Try Again      🔄", callback_data=f'quizgame_retry_from_file:{self.session_id}')])
        else:
            keyboard.append([InlineKeyboardButton("🔄      Try Again      🔄", callback_data=f'quizgame_try_again:{self.set_id}')])

        await self.context.bot.send_message(self.chat_id, text=score_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
        # === NAYA CODE ===
        # Ab hum final commentary ke liye AI ko trigger karenge
        asyncio.create_task(self.get_final_commentary_from_ai())

    # === NAYA FUNCTION (Class ke andar) ===
    async def get_final_commentary_from_ai(self):
        """Final commentary ke liye AI ko trigger karta hai aur context clean karta hai."""
        try:
            if self.chat_id not in user_chats: return
            chat_session = user_chats[self.chat_id]
            
            prompt_for_ai = (
                "The quiz has just finished. Your internal live report is now complete. "
                "Based on this final report, provide a fun, engaging, and personalized final commentary to the user. "
                "Congratulate them, mention their score, and encourage them to play again!"
            )
            
            await self.context.bot.send_chat_action(self.chat_id, 'typing')
            response = await chat_session.send_message_async(prompt_for_ai)
            
            # AI ke response ko user ko bhejo
            raw_chunks = response.text.split("\n---\n")
            for chunk in raw_chunks:
                stripped_chunk = chunk.strip()
                if stripped_chunk:
                    sanitized_chunk = sanitize_html(stripped_chunk)
                    await self.context.bot.send_message(
                        chat_id=self.chat_id, text=sanitized_chunk,
                        parse_mode=ParseMode.HTML, disable_web_page_preview=True
                    )
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to get final commentary from AI for user {self.chat_id}: {e}", exc_info=True)
        finally:
            # Bahut important: Commentary ke baad context hamesha clean karo
            await _remove_ai_quiz_context(self.chat_id)

# --- END OF UPDATED FILE quizzes/play_quiz.py ---
