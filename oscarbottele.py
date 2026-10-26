"""Telegram webhook receiver. No long-running polling or local database."""
import os, logging, threading, requests, time, secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort
from storage import db_request
from reporting import generate_report, generate_daily_report, send
from chi_mai import generate_chi_mai
from weekly_award import make_nomination, approve_award, publish_award
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
 if body and body.strip().split() and body.strip().split()[0].split("@")[0]=="/award_publish":
  sender=msg.get("from",{})
  if sender.get("id") in ADMINS and chat.get("type")=="private" and int(chat.get("id",0))==int(os.environ["CHAT_ID"]):
   if not REPORT_LOCK.acquire(blocking=False):
    telegram("sendMessage",{"chat_id":chat["id"],"text":"Đang xử lý tác vụ khác, hãy thử lại."})
   else:
    try:
     result=publish_award()
     telegram("sendMessage",{"chat_id":chat["id"],"text":"Giai Thương: "+result})
    except Exception:
     logging.exception("Manual award publication failed")
     telegram("sendMessage",{"chat_id":chat["id"],"text":"⚠️ Công bố chưa được xác nhận; kiểm tra nhóm và Render Logs trước khi thử lại."})
    finally:
     REPORT_LOCK.release()
  return "ok",200
 if body and body.strip().split() and body.strip().split()[0].split("@")[0]=="/award_refresh":
  sender=msg.get("from",{})
  if sender.get("id") in ADMINS and chat.get("type")=="private" and int(chat.get("id",0))==int(os.environ["CHAT_ID"]):
   telegram("sendMessage",{"chat_id":chat["id"],"text":"Oscar đang phân tích lại toàn bộ đề cử (loại anh Cường) và sẽ gửi riêng khi hoàn tất."})
   threading.Thread(target=refresh_award,daemon=True).start()
  return "ok",200
 if body and body.strip().split() and body.strip().split()[0].split("@")[0]=="/award":
  sender=msg.get("from",{})
  if sender.get("id") in ADMINS and chat.get("type")=="private" and int(chat.get("id",0))==int(os.environ["CHAT_ID"]):
   parts=body.strip().split()
   if len(parts)!=3:
    telegram("sendMessage",{"chat_id":chat["id"],"text":"Cú pháp: /award YYYY-MM-DD [số thứ tự bất kỳ hoặc skip]. Ngày là thứ Hai ghi trong bản đề cử."})
   elif not REPORT_LOCK.acquire(blocking=False):
    telegram("sendMessage",{"chat_id":chat["id"],"text":"Đang xử lý tác vụ khác, vui lòng thử lại."})
   else:
    try:
     result=approve_award(parts[1],parts[2])
     telegram("sendMessage",{"chat_id":chat["id"],"text":result})
    except Exception:
     logging.exception("Award approval failed")
     telegram("sendMessage",{"chat_id":chat["id"],"text":"Không thể xử lý công bố. Kiểm tra Render Logs; trước khi thử lại hãy kiểm tra xem nhóm đã nhận thông báo chưa."})
    finally:
     REPORT_LOCK.release()
  return "ok",200
 if body and body.strip().split() and body.strip().split()[0].split("@")[0]=="/rebuild_daily":
  sender=msg.get("from",{})
  if sender.get("id") in ADMINS and chat.get("type")=="private":
   import re
   from datetime import date
   parts=body.split()
   if len(parts) not in (2,3) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",parts[1]) or (len(parts)==3 and parts[2]!="send"):
    telegram("sendMessage",{"chat_id":chat["id"],"text":"Cú pháp: /rebuild_daily YYYY-MM-DD [send]. Không có send: preview riêng. Có send: phát lại vào nhóm."})
   else:
    try:
     target=date.fromisoformat(parts[1])
     if target>datetime.now(timezone(timedelta(hours=7))).date() or target.weekday()==6:
      raise ValueError("Ngày tương lai hoặc Chủ Nhật không hỗ trợ dựng lại báo cáo quản trị")
     threading.Thread(target=rebuild_daily,args=(target,len(parts)==3,),daemon=True).start()
     telegram("sendMessage",{"chat_id":chat["id"],"text":"Đã nhận yêu cầu dựng lại; bản preview sẽ gửi riêng nếu không có 'send'."})
    except ValueError as exc:
     telegram("sendMessage",{"chat_id":chat["id"],"text":str(exc)})
  return "ok",200
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
def refresh_award():
 try:
  make_nomination(force=True)
 except Exception:
  logging.exception("Award refresh failed")
  try:telegram("sendMessage",{"chat_id":int(os.environ["CHAT_ID"]),"text":"⚠️ Tạo lại đề cử thất bại. Kiểm tra Render Logs."})
  except Exception:logging.exception("Refresh failure notification failed")

def rebuild_daily(target_date,deliver_team):
 try:
  generate_daily_report(target_date=target_date,force=True,deliver_team=deliver_team)
 except Exception:
  logging.exception("Daily rebuild failed")
  try: telegram("sendMessage",{"chat_id":int(os.environ["CHAT_ID"]),"text":"⚠️ Dựng lại báo cáo thất bại. Kiểm tra Render Logs."})
  except Exception:logging.exception("Failed to notify admin")

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

@app_web.post("/cron/weekly-award")
def cron_weekly_award():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret):abort(403)
 if not REPORT_LOCK.acquire(blocking=False):return {"status":"busy"},409
 try:
  status=make_nomination()
  return {"status":status},200
 except Exception:
  logging.exception("Weekly nomination failed")
  return {"status":"error"},500
 finally:
  REPORT_LOCK.release()

@app_web.post("/cron/chi-mai")
def cron_chi_mai():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret):abort(403)
 if not REPORT_LOCK.acquire(blocking=False):return {"status":"busy"},409
 try:
  status=generate_chi_mai()
  return {"status":status},200
 except Exception:
  logging.exception("Chi Mai reminder failed")
  return {"status":"error"},500
 finally:
  REPORT_LOCK.release()

@app_web.post("/cron/test-delivery")
def cron_test_delivery():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret):abort(403)
 team_id=os.getenv("TEAM_REPORT_CHAT_ID","").strip()
 if not team_id:return {"status":"error","reason":"TEAM_REPORT_CHAT_ID missing"},500
 message="🧪 OSCAR — TEST DELIVERY\\nĐây là tin nhắn kiểm tra kênh nhận Morning Management Brief. Không phải báo cáo thật.\\nLịch báo cáo hiện tại: 08:00 (GMT+7)."
 results={}
 for label,recipient in (("team",team_id),("private",os.environ["CHAT_ID"])):
  try:
   send(message,chat_id=int(recipient))
   results[label]="sent"
  except Exception:
   logging.exception("Test delivery failed: %s",label)
   results[label]="failed"
 return {"status":"sent" if all(v=="sent" for v in results.values()) else "partial_failure","destinations":results},(200 if all(v=="sent" for v in results.values()) else 500)

@app_web.post("/cron/daily")
def cron_daily():
 secret=os.getenv("CRON_SECRET","")
 supplied=request.headers.get("X-Cron-Secret","")
 if not secret or not secrets.compare_digest(supplied,secret):abort(403)
 if not REPORT_LOCK.acquire(blocking=False):return {"status":"busy"},409
 try:
  from zoneinfo import ZoneInfo
  local=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
  if local.hour<8:return {"status":"skipped","reason":"Before 08:00 Vietnam time"},200
  # One-time corrective reissue for 19 Oct: the 07:00 brief lacked archived hourly data.
  # The normal daily checkpoint already exists, so bypass it once at/after 08:00.
  if local.date().isoformat()=="2026-10-19":
   marker="daily_rerun:2026-10-19"
   prior=db_request("report_state",params={"key":"eq."+marker,"select":"value"})
   if prior:return {"status":"skipped","reason":"Corrected October 19 brief already sent"},200
   result=generate_daily_report(target_date=local.date(),force=True,deliver_team=True)
   if result=="sent":
    db_request("report_state","POST",{"key":marker,"value":datetime.now(timezone.utc).isoformat()},params={"on_conflict":"key"},prefer="resolution=merge-duplicates,return=minimal")
   return {"status":result,"corrected":True},200
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
