# bot.py

# ... (baaki saara code upar ka same rahega) ...

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"Received message from {user.first_name}: '{message_text}'") # <-- Added a log to see if it's even being triggered

    # --- Start of Ping-Pong Test ---
    # Humne Gemini AI ke poore logic ko temporarily comment out kar diya hai
    try:
        await update.message.reply_text(f"Pong! I received your message: '{message_text}'")
        logger.info("Successfully sent 'Pong!' response.")
        return # Test ke liye yahan se return kar denge
    except Exception as e:
        logger.error(f"Error even in sending a simple reply: {e}", exc_info=True)
    # --- End of Ping-Pong Test ---


    # ===============================================
    # ===== ORIGINAL CODE (TEMPORARILY DISABLED) ====
    # ===============================================
    # if 'next_message_is' in context.user_data:
    #     state = context.user_data.pop('next_message_is')
    #     if user.id not in settings.user_profiles: settings.user_profiles[user.id] = {}
    #     settings.user_profiles[user.id][state] = message_text
    #     settings.save_user_profiles()
    #     await update.message.reply_text(f"✅ Theek hai, maine aapka '{state}' save kar liya hai! Main isse agle conversation se yaad rakhoonga.")
    #     if user.id in user_chats: del user_chats[user.id]
    #     return

    # await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    # chat_session = get_or_create_chat_session(user.id, user.first_name)
    # try:
    #     THREAD_LOCALS.context = context
    #     THREAD_LOCALS.loop = asyncio.get_running_loop()
    #     THREAD_LOCALS.context.update = update

    #     response = await chat_session.send_message_async(message_text)
        
    #     await update.message.reply_text(
    #         response.text,
    #         parse_mode=ParseMode.HTML,
    #         disable_web_page_preview=True
    #     )

    # except Exception as e:
    #     logger.error(f"Error handling message: {e}", exc_info=True)
    #     await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई ਹੈ।")
    # finally:
    #     if hasattr(THREAD_LOCALS, 'context'):
    #         del THREAD_LOCALS.context
    #     if hasattr(THREAD_LOCALS, 'loop'):
    #         del THREAD_LOCALS.loop
    # ===============================================

# ... (baaki saara code neeche ka same rahega) ...
