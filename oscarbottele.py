import anthropic
import logging
import datetime
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# CẤU HÌNH (Dán trực tiếp vào đây để bạn dễ quản lý)
TELEGRAM_TOKEN = '8850323891:AAE-zU9-SzGVA9epVxcHrJBnKSgjkoBdPS4'
CHAT_ID = '433260653' 
ANTHROPIC_API_KEY = 'sk-ant-api03-4ZA0Hw9ckvyrRybe4m3UfC5mdARtM2djCNmqae0zJzRjZLDatOONnFijC6lb3_Z308yb-vOmbY99in5tzjgnw-lkqsvAAA'

# Khởi tạo
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
message_history = []

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

async def analyze_and_report(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type in ['group', 'supergroup']:
        msg = f"[{update.effective_chat.title}] {update.message.from_user.first_name}: {update.message.text}"
        message_history.append(msg)
        if len(message_history) >= 20: 
            await trigger_analysis(context)

async def trigger_analysis(context: ContextTypes.DEFAULT_TYPE):
    global message_history
    if not message_history: return
    raw_logs = "\n".join(message_history)
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            system="Bạn là Strategic Consulting Director, phản hồi sắc bén và chuyên nghiệp.",
            messages=[{"role": "user", "content": f"Phân tích các rủi ro từ log sau:\n{raw_logs}"}]
        )
        await context.bot.send_message(chat_id=CHAT_ID, text=response.content[0].text)
        message_history.clear()
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    print("Bot đang chạy...")
    app.run_polling()