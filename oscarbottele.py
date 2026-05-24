import os
import threading
from flask import Flask
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import anthropic

# Lấy dữ liệu từ biến môi trường (Bảo mật tuyệt đối)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
recent_messages = []

# Hàm xử lý tin nhắn trong Group
async def analyze_and_report(update, context):
    if update.message and update.message.text:
        msg = f"{update.effective_user.first_name}: {update.message.text}"
        recent_messages.append(msg)

# Hàm báo cáo (Dùng chung cho cả tự động 1 tiếng và lệnh /baocao)
async def hourly_report(context: ContextTypes.DEFAULT_TYPE):
    if not recent_messages:
        await context.bot.send_message(chat_id=CHAT_ID, text="📊 Báo cáo: Không có tin nhắn mới nào để tổng hợp.")
    else:
        summary = "\n".join(recent_messages)
        try:
            # Sử dụng đúng model ID mà bạn đã cung cấp
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1000,
                messages=[{"role": "user", "content": f"Tổng hợp các vấn đề (issues) từ các tin nhắn sau: {summary}. Nếu không có issue, hãy báo 'Không có gì đáng lưu ý'"}]
            )
            msg = response.content[0].text
        except Exception as e:
            msg = f"Lỗi phân tích: {str(e)}"
        recent_messages.clear()
    
    if CHAT_ID:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"📊 Báo cáo:\n{msg}")

# Web server cho Render
app_web = Flask(__name__)
@app_web.route('/')
def index(): return 'Bot is running fine!', 200
def run_web(): app_web.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Lịch tự động mỗi 1 tiếng
    app.job_queue.run_repeating(hourly_report, interval=3600, first=60)
    
    # Handler tin nhắn
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    
    # Handler lệnh /baocao để gọi thủ công
    app.add_handler(CommandHandler("baocao", hourly_report))
    
    app.run_polling(drop_pending_updates=True)