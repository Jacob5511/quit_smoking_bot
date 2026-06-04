# 🍺❌ Quit Drinking Support Bot

A Telegram group moderation bot that:
- **Deletes spam/promotional messages** using Ollama (local LLM, no API costs)
- **Sends a welcome message** when someone types `+`

---

## 📁 Files

```
bot.py           ← main bot logic
requirements.txt ← Python dependencies
Dockerfile       ← builds the container (Ollama + Python)
start.sh         ← starts Ollama, pulls model, then starts bot
railway.toml     ← Railway deployment config
```

---

## 🔧 Step 1 — Create your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g. `Quit Drinking Support`)
4. Give it a username (e.g. `@myquitdrinkingbot`)
5. BotFather will give you a **token** like `123456:ABCdef...` — save it!

**Important:** After creating the bot:
- Go to BotFather → `/mybots` → your bot → *Bot Settings* → **Group Privacy → Turn OFF**
  (This lets the bot read all messages, not just commands)

---

## 👑 Step 2 — Add bot to your group as Admin

1. Add the bot to your Telegram group
2. Make it an **Admin** with permission to **Delete Messages**
   - Group → Edit → Administrators → Add Administrator → find your bot → enable "Delete Messages"

---

## 🚀 Step 3 — Deploy to Railway

### 3a. Push code to GitHub
```bash
git init
git add .
git commit -m "init"
# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 3b. Create Railway project
1. Go to **railway.app** and sign up / log in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repo
4. Railway will detect the Dockerfile automatically

### 3c. Set environment variables
In Railway → your service → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | `123456:ABCdef...` (from BotFather) |
| `OLLAMA_MODEL` | `llama3.2` (or `llama3.2:1b` for faster/cheaper) |
| `OLLAMA_URL` | `http://localhost:11434` |

### 3d. Deploy
Railway will build and deploy automatically. First deploy takes ~5 minutes (downloading the LLM model).

Check the **Logs** tab — you should see:
```
Ollama is up.
Pulling model: llama3.2...
Bot is running...
```

---

## 💰 Railway Cost Estimate

| Plan | Price | Notes |
|------|-------|-------|
| Hobby | ~$5/mo | Enough for this bot |

The bot uses ~500MB RAM at idle. `llama3.2:1b` is lighter if you hit memory limits.

---

## 🧪 Testing locally (optional)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2

# Install Python deps
pip install -r requirements.txt

# Set env var and run
BOT_TOKEN=your_token_here python bot.py
```

---

## ⚙️ Customisation

### Change the welcome message
Edit the `WELCOME_MESSAGE` variable in `bot.py`.

### Change spam detection sensitivity
Edit the `SPAM_CHECK_PROMPT` in `bot.py`. Add more examples of what counts as spam or legitimate.

### Use a lighter/faster model
Set `OLLAMA_MODEL=llama3.2:1b` in Railway variables. Uses less RAM, slightly less accurate.

### Notify user when their message is deleted
Uncomment the block in `handle_message()` in `bot.py`.

---

## 🛠 Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot doesn't delete messages | Make sure bot is Admin with "Delete Messages" permission |
| Bot doesn't read messages | Turn off Group Privacy in BotFather |
| Ollama timeout errors | Model is slow to respond — switch to `llama3.2:1b` |
| Bot crashes on Railway | Check Logs tab, may need more RAM — upgrade Railway plan |
