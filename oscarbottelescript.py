import anthropic
import logging
import datetime
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN, CHAT_ID, ANTHROPIC_API_KEY

# Khởi tạo Claude
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Lưu trữ log tạm thời
message_history = []

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

async def analyze_and_report(update, context: ContextTypes.DEFAULT_TYPE):
    # Chỉ thu thập tin nhắn từ các group
    if update.effective_chat.type in ['group', 'supergroup']:
        msg = f"[{update.effective_chat.title}] {update.message.from_user.first_name}: {update.message.text}"
        message_history.append(msg)
        
        # Tự động báo cáo nếu có quá nhiều tin nhắn (ví dụ 50 tin)
        if len(message_history) >= 50: 
            await trigger_analysis(context)

async def trigger_analysis(context: ContextTypes.DEFAULT_TYPE):
    global message_history
    if not message_history:
        return

    raw_logs = "\n".join(message_history)
    
    prompt = f"""
    Bạn là Strategic Consulting Director tại admeX. Đây là log hội thoại từ các group chat dự án:
    {raw_logs}
    
    Nhiệm vụ:
    1. CONTEXT: Tóm tắt ngắn gọn tình trạng dự án/công việc đang diễn ra.
    2. EXPERIENCE: Đánh giá cảm nhận của khách hàng hoặc nội bộ qua thái độ trong tin nhắn.
    3. EFFECTIVENESS: Chỉ ra đâu là "điểm nghẽn" (bottleneck) hoặc rủi ro thực sự.
    4. ACTION: Nếu có rủi ro, hãy đề xuất 1 hành động can thiệp cụ thể cho tôi (Director).
    
    Nếu mọi thứ ổn định, hãy trả về kết quả ngắn gọn: 'Tình hình ổn định, không có rủi ro cần can thiệp.'
    """
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            system="Bạn là trợ lý chiến lược, phản hồi sắc bén và chuyên nghiệp.",
            messages=[{"role": "user", "content": prompt}]
        )
        await context.bot.send_message(chat_id=CHAT_ID, text=response.content[0].text)
        message_history.clear()
    except Exception as e:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Hệ thống phân tích gặp lỗi: {str(e)}")

async def daily_digest(context: ContextTypes.DEFAULT_TYPE):
    if message_history:
        await trigger_analysis(context)
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text="Sáng nay không có vấn đề nào nghiêm trọng trong các group.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Lên lịch báo cáo hằng ngày vào 8:30 sáng
    job_queue = app.job_queue
    job_queue.run_daily(daily_digest, time=datetime.time(8, 30))
    
    # Xử lý tin nhắn
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_and_report))
    
    app.run_polling()