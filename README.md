# Oscar Telegram GPT V2 — Render Free architecture

- Render Free: Flask Telegram webhook receiver; no polling.
- Supabase Free: persistent PostgreSQL storage, auto group discovery.
- GitHub Actions: hourly reporting via OpenAI API, independent of Render uptime.
- Manual /baocao [1h|24h|7d]: private admin command (best-effort on Render Free).

## Setup (not yet live)
1. Create Supabase project and execute `schema.sql` in SQL Editor.
2. Render environment: TELEGRAM_TOKEN, CHAT_ID, ADMIN_USER_IDS, OPENAI_API_KEY, OPENAI_MODEL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_WEBHOOK_SECRET, PORT.
3. GitHub Actions repository secrets: TELEGRAM_TOKEN, CHAT_ID, OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY. Optional variable OPENAI_MODEL.
4. Deploy after merging reviewed PR. Set Telegram webhook to https://oscar-tele-bot.onrender.com/telegram/webhook using Telegram setWebhook with secret_token matching TELEGRAM_WEBHOOK_SECRET, allowed_updates ["message","edited_message","my_chat_member"]. Do not place bot token in a public URL or screenshot.
5. Disable Telegram bot privacy via BotFather, or grant admin rights, to receive ordinary group messages. Verify by sending a test message in a group.
6. Test /baocao privately and GitHub Actions workflow_dispatch; inspect logs.

## Constraints
- Render Free can sleep, introducing cold starts and potential webhook delivery gaps. Telegram retries but does not guarantee indefinite retention.
- GitHub scheduled workflows can run late or be skipped; not exact-hour SLA.
- Supabase Free has usage limits and may pause inactive projects.
- The reporter caps input to 1000 messages / 85k characters per run, and flags truncated reports. Longer reporting windows are best-effort.
- Group auto-discovery works when the bot receives a new group message or my_chat_member event; Telegram does not provide a complete historical group list.
- Report content is confidential: use a private admin chat ID and restrict access to Supabase service-role key.
- Keep PR draft until integration testing is complete.
