import os
import logging
import httpx
from telegram import Update, Message
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["8883715839:AAGOafSkj4pyRQIt6TA4c7VYlZT02sJ27cY"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

WELCOME_MESSAGE = """
👋 *Welcome to the Quit Drinking Support Group!*

Here you'll find people who understand what you're going through. You're not alone.

*Quick resources:*
🆘 Crisis line: 1-800-662-4357 (SAMHSA)
📖 /r/stopdrinking on Reddit
📱 AA Meeting finder: aa.org
💬 SMART Recovery: smartrecovery.org

*Group rules:*
✅ Be kind and supportive
✅ Share your experience
❌ No promotion or selling
❌ No shaming

*How long have you been sober?* Share below! Every day counts. 💪
""".strip()

SPAM_CHECK_PROMPT = """You are a moderation assistant for a quit-drinking support group on Telegram.

Your job: decide if a message is SPAM/PROMOTIONAL or LEGITIMATE.

SPAM/PROMOTIONAL means:
- Selling products, services, supplements, apps
- Advertising rehab centers or paid programs (unless just mentioning them casually)
- Crypto, forex, gambling, MLM
- "DM me", "check my bio/link", "join my channel"
- Generic motivational content with a link or call to action
- Anything that feels like an ad

LEGITIMATE means:
- Personal stories about quitting drinking
- Asking for help or advice
- Sharing struggles or victories
- Recommending free resources without a sales angle
- General chat and support

Message to classify:
\"\"\"
{message}
\"\"\"

Reply with ONLY one word: SPAM or LEGITIMATE"""


async def is_spam(text: str) -> bool:
    """Ask Ollama if a message is spam/promotional."""
    prompt = SPAM_CHECK_PROMPT.format(message=text[:1000])  # cap at 1000 chars
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
            )
            response.raise_for_status()
            result = response.json().get("response", "").strip().upper()
            logger.info(f"Ollama verdict for message: {result!r}")
            return result.startswith("SPAM")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return False  # if Ollama is down, don't delete


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message: Message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()

    # --- Handle "+" trigger ---
    if text == "+":
        await message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")
        return

    # --- Skip short messages (unlikely to be spam) ---
    if len(text) < 20:
        return

    # --- Spam check via Ollama ---
    if await is_spam(text):
        try:
            await message.delete()
            logger.info(f"Deleted spam from @{message.from_user.username}: {text[:80]}")
            # Optional: notify the user privately (comment out if you don't want this)
            # await context.bot.send_message(
            #     chat_id=message.from_user.id,
            #     text="Your message was removed from the group as it appeared promotional. "
            #          "If this was a mistake, please contact an admin."
            # )
        except Exception as e:
            logger.error(f"Could not delete message: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
