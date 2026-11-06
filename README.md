# Unified Telegram moderator

One Python process runs both existing Telegram bot identities, so Railway needs
only one service. Each bot may serve many groups. A group can use the bot's
default profile or override it with another profile.

## What is already configured

- `smoking` bot -> `quit_smoking` profile and the current smoking welcome link.
- `drinking` bot -> `quit_drinking` profile and the current drinking welcome link.
- `general_moderation` profile -> reusable moderation without a `+` business link.
- Admin decisions are stored in SQLite, so the buttons continue to work after a restart.
- If an administrator does not choose **Stays muted** or **Unmute** within 72
  hours, the review is automatically finalized as **Stays muted**. Set
  `REVIEW_TIMEOUT_MINUTES` to change that deadline.
- If two configuration entries contain the same Telegram token, the service
  automatically starts only one polling loop. Telegram does not allow two
  `getUpdates` pollers for one bot account.
- A callback is accepted only from that bot's configured admin.
- Text spam sent by non-admin bot accounts is deleted and the bot account is banned.
- Text spam posted on behalf of a channel is deleted and that channel identity is banned.
- Automatic copies of the linked channel's own posts and anonymous group-admin
  messages remain protected from these rules.

Both bot tokens remain separate. This keeps the existing bot usernames and
Telegram groups unchanged while combining their hosting.

## Railway variables

Create one Railway service from this folder/repository and add:

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-flash
DATABASE_PATH=/data/moderation.db
REVIEW_TIMEOUT_MINUTES=4320
SMOKING_BOT_TOKEN=...
SMOKING_ADMIN_ID=...
DRINKING_BOT_TOKEN=...
DRINKING_ADMIN_ID=...
BOTS_CONFIG_JSON=[{"name":"smoking","token_env":"SMOKING_BOT_TOKEN","admin_id_env":"SMOKING_ADMIN_ID","default_profile":"quit_smoking","chat_profiles":{}},{"name":"drinking","token_env":"DRINKING_BOT_TOKEN","admin_id_env":"DRINKING_ADMIN_ID","default_profile":"quit_drinking","chat_profiles":{}}]
```

Mount a Railway volume at `/data` and run exactly **one replica**. Two replicas
would poll Telegram with the same tokens and conflict.

After the combined service is confirmed working, stop the two old services.
Do not run an old service and this service with the same token at the same time.

## Use one bot differently in a particular group

Telegram chat IDs are negative numbers, usually beginning with `-100`. Put a
mapping in that bot's `chat_profiles`. For example, the smoking bot can keep its
normal behavior everywhere but use general moderation in one other group:

```json
[
  {
    "name": "smoking",
    "token_env": "SMOKING_BOT_TOKEN",
    "admin_id_env": "SMOKING_ADMIN_ID",
    "default_profile": "quit_smoking",
    "chat_profiles": {
      "-1001234567890": "general_moderation"
    }
  },
  {
    "name": "drinking",
    "token_env": "DRINKING_BOT_TOKEN",
    "admin_id_env": "DRINKING_ADMIN_ID",
    "default_profile": "quit_drinking",
    "chat_profiles": {}
  }
]
```

## Add another business or purpose

Add another entry to `profiles.json`. A custom profile may supply:

```json
{
  "another_business": {
    "moderation_mode": "custom",
    "system_prompt": "Your complete classification rules. Require exactly SPAM or LEGITIMATE.",
    "welcome_trigger": "+",
    "welcome_message": "This business's message and link",
    "keywords": ["known spam phrase"],
    "ai_enabled": true
  }
}
```

Then route a chat ID to `another_business` in `BOTS_CONFIG_JSON`. To change
profiles without committing a file, put the complete profiles object in the
optional Railway variable `PROFILES_JSON`.

You can also select a profile from Telegram. The configured administrator runs
the following once inside the relevant group or linked discussion group:

```text
/profile quit_smoking
/profile quit_drinking
/profile general_moderation
```

Running `/profile` without an argument shows the current profile, the chat ID,
and the available profiles. The selection is stored in SQLite and survives
deployments and restarts.

## Telegram limits

- Group moderation works when the bot is a group admin with permission to delete
  messages and restrict members, and BotFather privacy mode is disabled.
- To moderate messages authored by other bots, also enable **Bot-to-Bot
  Communication Mode** for the moderator in BotFather. Telegram normally does
  not deliver bot-authored group messages to another bot without that mode.
- Telegram channel comments are messages in the channel's linked discussion
  group. Add the bot there as an admin. Ordinary channel subscribers cannot post
  directly in a broadcast channel.
- A bot sees only chats where it has been added. This service does not combine
  the two Telegram identities or their BotFather settings; it only combines the
  process that runs them.

## Local verification

Copy `.env.example` to `.env`, use test credentials, then run:

```text
python -m unittest -v
python bot.py
```

The automated tests do not contact Telegram or DeepSeek. A final deployment
check should be performed in one test group before disabling the old services.

