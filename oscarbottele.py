import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import anthropic

# Lấy biến môi trường
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
recent_messages = []

async def analyze_and_report(update, context):
    # CHỈ xử lý nếu tin nhắn thực sự có văn bản (tránh lỗi NoneType)
    if update.message and update.message.text:
        msg = f"{update.effective_user.first_name}: {update.message.text}"
        recent_messages.append(msg)

async def hourly_report(context: ContextTypes.DEFAULT_TYPE):
    if not recent_messages:
        msg = "Không có gì đáng lưu ý trong tiếng vừa qua."
    else:
        summary = "\n".join(recent_messages)
        try:
            # Dùng tên model ngắn gọn hơn để tránh lỗi 404
            response = client.messages.create(
                model="claude-3-haiku", 
                max_tokens=1000,
                messages=[{"role": "user", "content": f"Tổng hợp issues từ các tin nhắn sau: {summary}"}]
            )
            msg = response.content[0].text
        except Exception as e:
            msg = f"Lỗi phân tích: {str(e)}"
        recent_messages.clear()
    
    if CHAT_ID:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"📊 Báo cáo định kỳ:\n{msg}")

app_web = Flask(__name__)
@app_web.route('/')
def index(): return 'Bot is running!'
def run_web(): app_web.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.job_queue.run_repeating(hourly_report, interval=3600, first=60)
    # Chỉ nhận tin nhắn có text
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    app.run_polling(drop_pending_updates=True)