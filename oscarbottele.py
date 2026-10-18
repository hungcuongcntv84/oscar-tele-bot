"""Telegram webhook receiver. No long-running polling or local database."""
import os, logging, threading, requests, time, secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
from storage import db_request
from reporting import generate_report, generate_daily_report
logging.basicConfig(level=logging.INFO)
app_web=Flask(__name__)
TOKEN=os.environ["TELEGRAM_TOKEN"]
SECRET=os.environ["TELEGRAM_WEBHOOK_SECRET"]
REPORT_LOCK=threading.Lock()
ADMINS={int(s.strip()) for s in os.environ["ADMIN_USER_IDS"].split(",") if s.strip()}
if not ADMINS: raise RuntimeError("ADMIN_USER_IDS required")
def telegram(method,payload):
 r=requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}",json=payload,timeout=20)
 r.raise_for_status()
 return r.json()
@app_web.route("/",methods=["GET","HEAD"])
def health(): return "Oscar bot webhook alive",200
@app_web.post("/telegram/webhook")
def webhook():
 if request.headers.get("X-Telegram-Bot-Api-Secret-Token")!=SECRET: abort(403)
 update=request.get_json(silent=True) or {}
 member=update.get("my_chat_member")
 if member:
  chat=member.get("chat",{})
  if chat.get("type") in ("group","supergroup"):
   status=member.get("new_chat_member",{}).get("status","")
   db_request("groups","POST",{"chat_id":chat["id"],"title":chat.get("title",""),"active":status not in ("left","kicked")},params={"on_conflict":"chat_id"},prefer="resolution=merge-duplicates,return=minimal")
 msg=update.get("message") or update.get("edited_message")
 if not msg:return "ok",200
 chat=msg.get("chat",{})
 body=msg.get("text") or msg.get("caption")
 if chat.get("type") in ("group","supergroup") and body:
  db_request("groups","POST",{"chat_id":chat["id"],"title":chat.get("title",""),"active":True},params={"on_conflict":"chat_id"},prefer="resolution=merge-duplicates,return=minimal")
  sender=msg.get("from",{})
  db_request("messages","POST",{"chat_id":chat["id"],"message_id":msg["message_id"],"title":chat.get("title",""),"sender":sender.get("first_name","Unknown"),"sent_at":datetime.fromtimestamp(msg["date"],timezone.utc).isoformat(),"body":body},params={"on_conflict":"chat_id,message_id"},prefer="resolution=ignore-duplicates,return=minimal")
 if body and body.strip().split() and body.strip().split()[0].split("@")[0]=="/baocao":
  sender=msg.get("from",{})
  if sender.get("id") in ADMINS and chat.get("type")=="private":
   parts=body.split()
   duration=parts[1] if len(parts)>1 else "1h"
   if duration not in ("1h","24h","7d"):
    telegram("sendMessage",{"chat_id":chat["id"],"text":"Cú pháp: /baocao, /baocao 24h, /baocao 7d"})
    return "ok",200
   telegram("sendMessage",{"chat_id":chat["id"],"text":"Đang phân tích báo cáo..."})
   threading.Thread(target=manual_report,args=(duration,),daemon=True).start()
 return "ok",200
def manual_report(duration):
 try: generate_report(duration,scheduled=False)
 except Exception:
  logging.exception("Manual report failed")
  try: telegram("sendMessage",{"chat_id":int(os.environ["CHAT_ID"]),"text":"⚠️ Oscar GPT: báo cáo theo yêu cầu thất bại. Kiểm tra Render Logs."})
  except Exception: logging.exception("Failed to notify admin")
@app_web.post("/cron/hourly")
def cron_hourly():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret): abort(403)
 if not REPORT_LOCK.acquire(blocking=False):
  return {"status":"busy"},409
 try:
  rows=db_request("report_state",params={"key":"eq.hourly","select":"value"})
  if rows:
   last=datetime.fromisoformat(rows[0]["value"])
   if last.tzinfo is None: last=last.replace(tzinfo=timezone.utc)
   elapsed=(datetime.now(timezone.utc)-last).total_seconds()
   if elapsed<3300:
    return {"status":"skipped","reason":"last successful report less than 55 minutes ago"},200
  generate_report("1h",scheduled=True)
  return {"status":"sent"},200
 except Exception:
  logging.exception("Scheduled cron report failed")
  return {"status":"error"},500
 finally:
  REPORT_LOCK.release()

@app_web.post("/cron/daily")
def cron_daily():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret):abort(403)
 if not REPORT_LOCK.acquire(blocking=False):return {"status":"busy"},409
 try:
  from zoneinfo import ZoneInfo
  local=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
  if local.hour<7:return {"status":"skipped","reason":"Before 07:00 Vietnam time"},200
  result=generate_daily_report()
  return {"status":result},200
 except Exception:
  logging.exception("Daily report failed")
  return {"status":"error"},500
 finally:
  REPORT_LOCK.release()

def register_webhook():
 url=os.environ.get("WEBHOOK_PUBLIC_URL","https://oscar-tele-bot.onrender.com").rstrip("/")+"/telegram/webhook"
 for attempt in range(5):
  try:
   result=telegram("setWebhook",{"url":url,"secret_token":SECRET,"allowed_updates":["message","edited_message","my_chat_member"],"drop_pending_updates":False})
   if not result.get("ok"):raise RuntimeError(str(result))
   logging.info("Telegram webhook registered")
   return
  except Exception:
   logging.exception("Webhook registration attempt %s failed",attempt+1)
   time.sleep(min(2**attempt,20))
 logging.error("Webhook registration failed; inspect logs and re-deploy")
if __name__=="__main__":
 threading.Thread(target=register_webhook,daemon=True).start()
 app_web.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
