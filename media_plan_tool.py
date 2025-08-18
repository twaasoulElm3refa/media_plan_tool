
import os
import json
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# === Import DB helpers from separate module ===
from database import (
    get_db_connection,
    fetch_latest_result,
    save_result,
)

load_dotenv()
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# 1) Try to import your function
# =========================
try:
    def media_plan(data, emergency_plan= None):
      if emergency_plan==None:
          prompt=f'''أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.
              1. الهدف الإعلامي
              2. الجمهور المستهدف
              3. الرسائل المفتاحية
              4. المنصات المقترحة
              5. أنواع المحتوى (منشورات – فيديو – إنفوجرافيك – تقارير – مقالات)
              6. الجدول الزمني (تقسيم زمني واضح بالأسابيع أو الأشهر)
              7. المؤشرات الرقمية المستهدفة (نسبة تفاعل، عدد زيارات، زيادة متابعين، إلخ)
              8. الموازنة التقديرية (حسب خيارات المستخدم)
              9. التوصيات العامة (مثل: التعاون مع مؤثرين – حملات ممولة – تحسين البروفايل)
              '''
      else:
          prompt=f'''أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.
              1. الهدف الإعلامي
              2. الجمهور المستهدف
              3. الرسائل المفتاحية
              4. المنصات المقترحة
              5. أنواع المحتوى (منشورات – فيديو – إنفوجرافيك – تقارير – مقالات)
              6. الجدول الزمني (تقسيم زمني واضح بالأسابيع أو الأشهر)
              7. المؤشرات الرقمية المستهدفة (نسبة تفاعل، عدد زيارات، زيادة متابعين، إلخ)
              8. الموازنة التقديرية (حسب خيارات المستخدم)
              9. التوصيات العامة (مثل: التعاون مع مؤثرين – حملات ممولة – تحسين البروفايل)
              10. خطة طوارئ أو إدارة أزمة (اختياري)
              '''
          
      new_data= f'''أنشئ خطة إعلامية مدفوعة تفصيلية قابلة للتنفيذ بناءً على البيانات التالية :{data}
      راعي هذه النقاط 
      كيف تعزز الـ Prompt ليعالج هذه الفجوات:
  
      عشان تخرج خطة مثل اللي تتصورها، لازم توضح في الـ Prompt أن المطلوب إلزاميًا يتضمن:
      
      جدول Placement كامل: Platform | Market (مدينة) | Section/Target | Language | Estimated Impressions | Actual Net Cost | Demographics | Interests/Behaviors | Duration (أيام).
      
      Event Phasing: (قبل / أثناء / بعد الحدث) مع أهداف وميزانية لكل مرحلة.
      
      LinkedIn Job Titles: أدرج بعض مسمى وظيفي.
      
      Channel-level Targets: Leads / Clicks / ROAS لكل قناة في مرحلة Conversion.
      
      Geo Split + Language Split: توزيع الميزانية حسب المدن واللغات.
      
      Google & TikTok: تضمينها كجزء من funnel strategy.
      
      Ops Recommendations: Facebook–Instagram integration + WhatsApp Remarketing.
      
      KPI by Channel: CPM / CTR / VTR / CPC / CPA / ROAS (قيم مستهدفة رقمية).
      
      3D Budget Matrix: (فئة × قناة × Funnel).
      
      Cadence: مدة Placement بالأيام + Creative Refresh كل 10–14 يوم.
      
      Bidding Strategy: Lowest-Cost كبداية ثم Cost Cap.
      
   '''
      response = client.chat.completions.create(
          model="gpt-4o",
          messages=[
              {"role": "system", "content":prompt },
              {"role": "user", "content":new_data },
          ],
      )
      return response.choices[0].message.content
except Exception:
    def media_plan(data, emergency_plan=None):
        return (
            "نتيجة تجريبية (Stub) — لم يتم استيراد media_plan الحقيقية.\n\n"
            f"emergency_plan={emergency_plan}\n"
            f"data keys: {list(data.keys())}"
        )

# =========================
# 2) Config
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# =========================
# 3) Schemas
# =========================
class StartPayload(BaseModel):
    request_id: int = Field(..., description="ID created by WordPress insert")
    user_id: int
  
    organization_name: Optional[str] = None
    media_campaign_name: Optional[str] = None
    type_of_entity: Optional[str] = None
    target_sector: Optional[str] = None
    target_age: Optional[int] = None
    target_geographic_location: Optional[str] = None
    interests: Optional[str] = None
    goals: Optional[str] = None
    campaign_budget: Optional[str] = None
    campaign_duration: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    platforms: Optional[str] = None  # CSV as sent by WP
    tone_of_speech: Optional[str] = None
    content_language: Optional[str] = None
    visual_identity: Optional[int] = 0
    is_there_a_prior_plan: Optional[int] = 0
    sponsored_campaigns: Optional[int] = 0

    emergency_plan: Optional[str] = None

class ResultRequest(BaseModel):
    request_id: int

class ApiStatus(BaseModel):
    status: str
    result: Optional[str] = None
    message: Optional[str] = None

# =========================
# 4) FastAPI app
# =========================
app = FastAPI(title="Media Plan API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 5) Background processor
# =========================
def process_job(payload: StartPayload):
    """
    Run the heavy media_plan() then store into DB.
    """
    try:
        plan_text = media_plan(payload.model_dump(), emergency_plan=payload.emergency_plan)
        if not isinstance(plan_text, str):
            plan_text = json.dumps(plan_text, ensure_ascii=False)

        save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
    except Exception as e:
        # In production, log properly (Sentry/Cloud logs)
        print("process_job error:", repr(e))

# =========================
# 6) Routes
# =========================
@app.on_event("startup")
def startup():
    ensure_results_table()

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.post("/start", response_model=ApiStatus)
def start_job(payload: StartPayload, bg: BackgroundTasks):
    """
    Accepts WordPress payload + request_id.
    Kicks off background processing and immediately returns "processing".
    If already exists, returns "done".
    """
    if payload.request_id <= 0 or payload.user_id <= 0:
        raise HTTPException(status_code=400, detail="request_id and user_id are required and must be > 0")

    existing = fetch_latest_result(payload.request_id)
    if existing:
        return {"status": "done", "result": existing["edited_result"] or existing["result"]}

    bg.add_task(process_job, payload)
    return {"status": "processing"}

@app.post("/result", response_model=ApiStatus)
def get_result(req: ResultRequest):
    """
    WordPress polls with {request_id}.
    Returns processing/done.
    """
    if req.request_id <= 0:
        raise HTTPException(status_code=400, detail="request_id is required and must be > 0")

    row = fetch_latest_result(req.request_id)
    if not row:
        return {"status": "processing"}

    return {"status": "done", "result": row["edited_result"] or row["result"]}
