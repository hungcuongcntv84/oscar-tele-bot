import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import anthropic

# Lấy dữ liệu từ cấu hình Cloud
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Hàm xử lý tin nhắn
async def analyze_and_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_title = update.effective_chat.title or "Private Chat"
    
    # Gửi qua Claude để phân tích (Ví dụ tư duy ConteXtive)
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1000,
        messages=[{"role": "user", "content": f"Phân tích chiến lược tin nhắn này trong {chat_title}: {user_text}"}]
    )
    
    # Phản hồi lại (bạn có thể đổi thành gửi cho chính bạn)
    await update.message.reply_text(response.content[0].text)

if __name__ == '__main__':
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        print("LỖI: Chưa thiết lập biến môi trường (Token/API Key)!")
    else:
        print("Bot đang chạy...")
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
        app.run_polling(drop_pending_updates=True)