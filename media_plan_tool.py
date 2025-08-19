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
def media_plan(data, emergency_plan=None):
    if emergency_plan is None:
        prompt = (
            "أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.\n"
            "قدّم خطة تتضمن: "
            "1) الهدف الإعلامي، 2) الجمهور المستهدف، 3) الرسائل المفتاحية، "
            "4) المنصات المقترحة، 5) أنواع المحتوى، 6) الجدول الزمني، "
            "7) المؤشرات الرقمية المستهدفة، 8) الموازنة التقديرية، 9) التوصيات العامة."
        )
    else:
        prompt = (
            "أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.\n"
            "قدّم خطة تتضمن: "
            "1) الهدف الإعلامي، 2) الجمهور المستهدف، 3) الرسائل المفتاحية، "
            "4) المنصات المقترحة، 5) أنواع المحتوى، 6) الجدول الزمني، "
            "7) المؤشرات الرقمية المستهدفة، 8) الموازنة التقديرية، "
            "9) التوصيات العامة، 10) خطة طوارئ أو إدارة أزمة."
        )

    new_data = (
        "أنشئ خطة إعلامية مدفوعة تفصيلية قابلة للتنفيذ بناءً على البيانات التالية:\n"
        f"{data}\n\n"
        "إلزامي تضمين:\n"
        "- جدول Placement: Platform | Market | Section/Target | Language | Estimated Impressions | "
        "Actual Net Cost | Demographics | Interests/Behaviors | Duration (أيام)\n"
        "- Event Phasing: قبل/أثناء/بعد مع أهداف وميزانية لكل مرحلة\n"
        "- LinkedIn Job Titles\n"
        "- Channel-level Targets: Leads/Clicks/ROAS\n"
        "- Geo + Language Split\n"
        "- تضمين Google & TikTok ضمن funnel\n"
        "- Ops Recommendations: Facebook–Instagram + WhatsApp Remarketing\n"
        "- KPI by Channel: CPM/CTR/VTR/CPC/CPA/ROAS بأرقام مستهدفة\n"
        "- 3D Budget Matrix: فئة × قناة × Funnel\n"
        "- Cadence: مدة Placement + Creative Refresh كل 10–14 يوم\n"
        "- Bidding Strategy: Lowest-Cost ثم Cost Cap\n"
    )

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": new_data},
        ],
    )
    return resp.choices[0].message.content

# =========================
# 2) Config
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# =========================
# 3) Schemas (Pydantic v1)
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
    platforms: Optional[str] = None   # CSV from WP
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
'''def process_job(payload: StartPayload):
    """
    Run media_plan() then store into DB.
    """
    try:
        # Pydantic v1:
        plan_text = media_plan(payload.dict(), emergency_plan=payload.emergency_plan)
        if not isinstance(plan_text, str):
            plan_text = json.dumps(plan_text, ensure_ascii=False)
        save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
    except Exception as e:
        print("process_job error:", repr(e))'''
def process_job(payload: StartPayload):
    try:
        plan_text = media_plan(payload.model_dump(), emergency_plan=payload.emergency_plan)
        if not isinstance(plan_text, str):
            plan_text = json.dumps(plan_text, ensure_ascii=False)
        save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
    except Exception as e:
        print("process_job error:", repr(e))


# =========================
# 6) Routes
# =========================
@app.on_event("startup")
def startup():
    get_db_connection()

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.post("/start", response_model=ApiStatus)
def start_job(payload: StartPayload, bg: BackgroundTasks):
    """
    Accepts WordPress payload + request_id.
    Kicks off background processing and immediately returns 'processing'.
    If already exists, returns 'done'.
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
    WordPress polls with {request_id}. Returns processing/done.
    """
    if req.request_id <= 0:
        raise HTTPException(status_code=400, detail="request_id is required and must be > 0")

    row = fetch_latest_result(req.request_id)
    if not row:
        return {"status": "processing"}

    return {"status": "done", "result": row["edited_result"] or row["result"]}



