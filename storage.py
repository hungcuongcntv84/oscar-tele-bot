"""Supabase PostgREST client using service-role key, server-side only."""
import os,requests
URL=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/"
KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
def db_request(table,method="GET",payload=None,params=None,prefer=None):
 headers={"apikey":KEY,"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}
 if prefer: headers["Prefer"]=prefer
 r=requests.request(method,URL+table,headers=headers,json=payload,params=params,timeout=30)
 r.raise_for_status()
 return r.json() if r.content else []
