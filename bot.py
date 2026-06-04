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
from dotenv import load_dotenv
load_dotenv()  # loads .env before os.environ reads

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

WELCOME_MESSAGE = """
Зарегистрироваться на мастер-класс можно здесь:
https://bothelp.cc/mini?domain=allencarrlife&id=3
""".strip()

SPAM_CHECK_PROMPT = """
You are a Telegram group moderator for a Russian speaking chat.

Your job is ONLY to detect obvious spam or abusive content.

Rules:
- If the message is a normal greeting (like "Привет", "Здравствуйте", "Как дела") → LEGITIMATE
- If the message is short but normal human input → LEGITIMATE
- If the message is random keyboard spam (like "asdkj123", "аааааааа", "qweqweqwe") → SPAM
- If the message contains advertising, selling, links, or promotion → SPAM
- If the message contains insults or harassment → SPAM

IMPORTANT:
- Do NOT guess hidden intent.
- Do NOT assume spam without clear signals.
- Be conservative: if unsure → LEGITIMATE.

Return ONLY JSON:
{"label": "SPAM"} or {"label": "LEGITIMATE"}
"""


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
            result = response.json().get("label", "").strip().upper()
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

    if update.message.chat.type != "group":
        return

    if message.from_user.is_bot:
        return

    # --- Spam check via Ollama ---
    result = await is_spam(text)
    if result:
        try:
            await message.delete()
            logger.info(f"Deleted spam from @{message.from_user.username}: {text[:80]} "
                        f"with a reson {result}\n{message.text}")
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
