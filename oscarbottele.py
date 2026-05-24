import os
import threading
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import anthropic

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
recent_messages = []

# Khởi tạo Application toàn cục để webhook có thể dùng
app = Application.builder().token(TELEGRAM_TOKEN).build()

async def analyze_and_report(update, context):
    if update.message and update.message.text:
        msg = f"{update.effective_user.first_name}: {update.message.text}"
        recent_messages.append(msg)

async def error_handler(update, context):
    pass

async def hourly_report(context: ContextTypes.DEFAULT_TYPE):
    msg = "Không có gì đáng lưu ý trong tiếng vừa qua."
    if recent_messages:
        summary = "\n".join(recent_messages)
        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1000,
                messages=[{"role": "user", "content": f"Tổng hợp issues: {summary}"}]
            )
            msg = response.content[0].text
        except Exception as e:
            msg = f"Lỗi phân tích: {str(e)}"
        recent_messages.clear()
    if CHAT_ID:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"📊 Báo cáo:\n{msg}")

app_web = Flask(__name__)

@app_web.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Xử lý webhook từ Telegram
        update = Update.de_json(request.get_json(force=True), app.bot)
        asyncio.run_coroutine_threadsafe(app.process_update(update), app.loop)
        return 'OK', 200
    return 'Bot is running fine!', 200

if __name__ == '__main__':
    # Đăng ký các handler
    app.job_queue.run_repeating(hourly_report, interval=3600, first=60)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    app.add_handler(CommandHandler("baocao", hourly_report))
    app.add_error_handler(error_handler)

    # Chạy Application ở chế độ nền (không dùng run_polling vì đã dùng webhook)
    loop = asyncio.get_event_loop()
    app.initialize()
    app.start()
    app.updater.start_polling() # Vẫn dùng polling để đảm bảo tính ổn định trên Render
    
    # Chạy Web Server
    app_web.run(host='0.0.0.0', port=10000)