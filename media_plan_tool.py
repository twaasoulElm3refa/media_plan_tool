import os
import json
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI

# === DB helpers from your separate file ===
from database import (
    get_db_connection,
    fetch_latest_result,
    save_result,
)

# ---- env & OpenAI ----
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# 1) media_plan implementation (uses OpenAI)
# =========================
def media_plan(data, emergency_plan=False):
    """
    Generate a media plan using OpenAI.
    """
    print("Received data for media plan:", data)

    # Define the prompt based on the plan
    prompt =f'''أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.
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
    if emergency_plan :
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
    
    # Construct the new data that will be passed to OpenAI
    new_data = f'''أنشئ خطة إعلامية مدفوعة تفصيلية قابلة للتنفيذ بناءً على البيانات التالية :{data}
    راعي هذه النقاط 
        كيف تعزز الـ Prompt ليعالج هذه الفجوات:
        عشان تخرج خطة مثل اللي تتصورها، لازم توضح في الـ Prompt أن المطلوب إلزاميًا يتضمن:
    
    جدول Placement كامل: Platform | Market (مدينة) | Section/Target | Language | Estimated Impressions | Actual Net Cost | Demographics | Interests/Behaviors | Duration (أيام).
    
    Event Phasing: (قبل / أثناء / بعد الحدث) مع أهداف وميزانية لكل مرحلة.
    
    LinkedIn Job Titles: أدرج 10–15 مسمى وظيفي.
    
    Channel-level Targets: Leads / Clicks / ROAS لكل قناة في مرحلة Conversion.
    
    Geo Split + Language Split: توزيع الميزانية حسب المدن واللغات.
    
    Google & TikTok: تضمينها كجزء من funnel strategy.
    
    Ops Recommendations: Facebook–Instagram integration + WhatsApp Remarketing.
    
    KPI by Channel: CPM / CTR / VTR / CPC / CPA / ROAS (قيم مستهدفة رقمية).
    
    3D Budget Matrix: (فئة × قناة × Funnel).
    
    Cadence: مدة Placement بالأيام + Creative Refresh كل 10–14 يوم.
    
    Bidding Strategy: Lowest-Cost كبداية ثم Cost Cap.
    '''

    # Send the request to OpenAI API
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": new_data},
        ],
    )

    result = response.choices[0].message.content
    print("Generated plan:", result)
    return result

# =========================
# 2) Config
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# =========================
# 3) Schemas (Pydantic v2)
# =========================
class StartPayload(BaseModel):
    request_id: int = Field(..., description="ID created by WordPress insert")
    user_id: int

    organization_name: Optional[str] = None
    media_campaign_name: Optional[str] = None
    type_of_entity: Optional[str] = None
    target_sector: Optional[str] = None
    target_age_start: Optional[int] = None  # nullable int
    target_age_end: Optional[int] = None  # nullable int
    target_geographic_location: Optional[str] = None
    interests: Optional[str] = None
    goals: Optional[str] = None
    campaign_budget: Optional[str] = None
    campaign_duration: Optional[str] = None  # Should be a string (text)
    start_date: Optional[str] = None  # Date as string (YYYY-MM-DD)
    end_date: Optional[str] = None  # Date as string (YYYY-MM-DD)
    platforms: Optional[str] = None  # String of platforms
    tone_of_speech: Optional[str] = None
    content_language: Optional[str] = None
    visual_identity: Optional[int] = 0  # tinyint(1), default 0
    is_there_a_prior_plan: Optional[int] = 0  # tinyint(1), default 0
    sponsored_campaigns: Optional[int] = 0  # tinyint(1), default 0
    emergency_plan: Optional[int] = 0  # tinyint(1), default 0 (1 for true, 0 for false)
    date: Optional[str] = None  # Date as string (YYYY-MM-DD)
    
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
    Run the media_plan function and save the result to the DB.
    """
    try:
        # Call media_plan to get the result
        plan_text = media_plan(payload.dict(), emergency_plan=payload.emergency_plan)

        # If the result isn't a string, convert it into one
        if not isinstance(plan_text, str):
            plan_text = json.dumps(plan_text, ensure_ascii=False)
        
        # Save result in the database
        save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
    except Exception as e:
        print("process_job error:", repr(e))

# =========================
# 6) Routes
# =========================
@app.on_event("startup")
def startup():
    # Ensure the database connection is made at startup
    get_db_connection()

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.post("/start", response_model=ApiStatus)
def start_job(payload: StartPayload, bg: BackgroundTasks):
    """
    Receives data from WordPress, processes it, and returns a status.
    Starts the background task to process the media plan.
    """
    if payload.request_id <= 0 or payload.user_id <= 0:
        raise HTTPException(status_code=400, detail="request_id and user_id are required and must be > 0")

    # Check if the result already exists for the request_id
    existing = fetch_latest_result(payload.request_id)
    if existing:
        return {"status": "done", "result": existing["edited_result"] or existing["result"]}

    # If no existing result, start the background job to process the media plan
    bg.add_task(process_job, payload)
    return {"status": "processing"}

@app.post("/result", response_model=ApiStatus)
def get_result(req: ResultRequest):
    """
    Allows WordPress to poll for the result of a job based on the request_id.
    Returns 'processing' or 'done' status.
    """
    if req.request_id <= 0:
        raise HTTPException(status_code=400, detail="request_id is required and must be > 0")

    # Fetch the latest result based on request_id
    row = fetch_latest_result(req.request_id)
    if not row:
        return {"status": "processing"}

    return {"status": "done", "result": row["edited_result"] or row["result"]}


