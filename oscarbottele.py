import os
import threading
from flask import Flask
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import anthropic

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
recent_messages = []

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
            # Giữ nguyên model yêu cầu
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
@app_web.route('/')
def index(): return 'Bot is running fine!', 200

def run_web(): 
    app_web.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    # Chạy Web Server trong luồng riêng để giữ bot luôn 'Live' trên Render
    threading.Thread(target=run_web, daemon=True).start()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Đăng ký Job và Handlers
    app.job_queue.run_repeating(hourly_report, interval=3600, first=60)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    app.add_handler(CommandHandler("baocao", hourly_report))
    app.add_error_handler(error_handler)
    
    # Chạy bot polling (không chạy app_web.run ở đây nữa)
    app.run_polling(drop_pending_updates=True)