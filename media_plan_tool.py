import os
import json
import time
import uuid
import base64
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
import jwt  # PyJWT

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
    print("Received data for media plan: successfully ✅")

    prompt = f'''أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.
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
    if emergency_plan:
        prompt = f'''أنت خبير Paid Media Buying & Distribution لعلامات استهلاكية.
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": new_data},
        ],
    )

    result = response.choices[0].message.content
    print("Generated plan successfully ✅")
    return result

# =========================
# 2) Config
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

def _load_jwt_secret() -> bytes:
    s = os.getenv("JWT_SECRET", "")
    if not s:
        raise RuntimeError("JWT_SECRET env var is required for /session and /chat")
    # accept raw or base64url-encoded (like your example)
    try:
        decoded = base64.urlsafe_b64decode(s)
        if len(decoded) >= 32:
            return decoded
    except Exception:
        pass
    return s.encode("utf-8")

JWT_SECRET = _load_jwt_secret()

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
    target_age_start: Optional[int] = None
    target_age_end: Optional[int] = None
    target_geographic_location: Optional[str] = None
    interests: Optional[str] = None
    goals: Optional[str] = None
    campaign_budget: Optional[str] = None
    campaign_duration: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    platforms: Optional[str] = None
    tone_of_speech: Optional[str] = None
    content_language: Optional[str] = None
    visual_identity: Optional[int] = 0
    is_there_a_prior_plan: Optional[int] = 0
    sponsored_campaigns: Optional[int] = 0
    emergency_plan: Optional[int] = 0
    date: Optional[str] = None

class ResultRequest(BaseModel):
    request_id: int

class ApiStatus(BaseModel):
    status: str
    result: Optional[str] = None
    message: Optional[str] = None

# ------ NEW: chat models ------
class SessionIn(BaseModel):
    user_id: int
    wp_nonce: Optional[str] = None

class SessionOut(BaseModel):
    session_id: str
    token: str

class VisibleValue(BaseModel):
    # minimal, extensible set for media plan
    id: Optional[int] = None
    organization_name: Optional[str] = None
    media_campaign_name: Optional[str] = None
    goals: Optional[str] = None
    platforms: Optional[str] = None
    target_geographic_location: Optional[str] = None
    article: Optional[str] = None  # the latest generated plan text the plugin stores in localStorage

class ChatIn(BaseModel):
    session_id: str
    user_id: int
    message: str
    visible_values: List[VisibleValue] = Field(default_factory=list)

# =========================
# 4) FastAPI app
# =========================
app = FastAPI(title="Media Plan API", version="1.2.0")

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
    try:
      plan_text = media_plan(payload.dict(), emergency_plan=bool(payload.emergency_plan))
      if not isinstance(plan_text, str):
          plan_text = json.dumps(plan_text, ensure_ascii=False)
      save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
      print(f"[JOB] saved result for #{payload.request_id} (len={len(plan_text)})")
    except Exception as e:
      err = f"ERROR: {type(e).__name__}: {e}"
      print("[JOB] OpenAI/processing failed:", err)
      try:
          save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=err)
      except Exception as e2:
          print("[JOB] save_result also failed:", repr(e2))

# =========================
# 6) Helpers for chat
# =========================
def _make_jwt(session_id: str, user_id: int) -> str:
    payload = {
        "sid": session_id,
        "uid": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 2,  # 2 hours
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def _verify_jwt(bearer: Optional[str]):
    if not bearer or not bearer.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = bearer.split(" ", 1)[1]
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def _values_to_context(values: List[VisibleValue]) -> str:
    if not values:
        return "لا توجد بيانات مرئية حالياً لهذا المستخدم."
    v = values[0]
    parts = []
    if v.organization_name:          parts.append(f"الجهة: {v.organization_name}")
    if v.media_campaign_name:        parts.append(f"اسم الحملة: {v.media_campaign_name}")
    if v.goals:                      parts.append(f"الأهداف: {v.goals}")
    if v.platforms:                  parts.append(f"المنصات: {v.platforms}")
    if v.target_geographic_location: parts.append(f"الموقع الجغرافي: {v.target_geographic_location}")
    if v.article:                    parts.append("**تم تمرير أحدث نص للخطة لمرجعية الإجابة.**")
    text = " | ".join(parts) if parts else "لا توجد تفاصيل كافية."
    # Append article separately to avoid making the header too long
    if v.article:
        text += f"\n---\nالنص المرجعي (الخطة الحالية):\n{v.article[:6000]}"  # cap to avoid huge prompts
    return text

# =========================
# 7) Routes
# =========================
@app.on_event("startup")
def startup():
    get_db_connection()

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.post("/start", response_model=ApiStatus)
def start_job(payload: StartPayload, bg: BackgroundTasks):
    if payload.request_id <= 0 or payload.user_id <= 0:
        raise HTTPException(status_code=400, detail="request_id and user_id are required and must be > 0")

    existing = fetch_latest_result(payload.request_id)
    if existing:
        return {"status": "done", "result": existing["edited_result"] or existing["result"]}

    bg.add_task(process_job, payload)
    return {"status": "processing"}

@app.post("/start_sync", response_model=ApiStatus)
def start_job_sync(payload: StartPayload):
    if payload.request_id <= 0 or payload.user_id <= 0:
        raise HTTPException(status_code=400, detail="request_id and user_id must be > 0")
    try:
        existing = fetch_latest_result(payload.request_id)
        if existing:
            return {"status": "done", "result": existing["edited_result"] or existing["result"]}

        plan_text = media_plan(payload.dict(), emergency_plan=bool(payload.emergency_plan))
        if not isinstance(plan_text, str):
            plan_text = json.dumps(plan_text, ensure_ascii=False)

        save_result(request_id=payload.request_id, user_id=payload.user_id, result_text=plan_text)
        return {"status": "done", "result": plan_text}
    except Exception as e:
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}

@app.post("/result", response_model=ApiStatus)
def get_result(req: ResultRequest):
    if req.request_id <= 0:
        raise HTTPException(status_code=400, detail="request_id is required and must be > 0")

    row = fetch_latest_result(req.request_id)
    if not row:
        return {"status": "processing"}

    text = row["edited_result"] or row["result"] or ""
    if text.startswith("ERROR:"):
        return {"status": "error", "message": text}
    return {"status": "done", "result": text}

# -------- NEW: Chat session + streaming chat --------
@app.post("/session", response_model=SessionOut)
def create_session(body: SessionIn):
    if body.user_id <= 0:
        raise HTTPException(status_code=400, detail="user_id is required")
    sid = str(uuid.uuid4())
    token = _make_jwt(sid, body.user_id)
    return SessionOut(session_id=sid, token=token)

@app.post("/chat")
def chat(body: ChatIn, authorization: Optional[str] = Header(None)):
    # Verify JWT
    _verify_jwt(authorization)

    # Build context from visible values provided by WP
    context = _values_to_context(body.visible_values)
    sys_prompt = (
        "أنت مساعد موثوق يجيب بالاعتماد على البيانات المرئية الحالية للمستخدم. "
        "إن لم تتوفر المعلومة في البيانات المرئية فاذكر ذلك واقترح كيف يمكن الحصول عليها.\n\n"
        f"البيانات المرئية:\n{context}"
    )
    user_msg = body.message or ""

    def stream():
        # OpenAI chat streaming
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            stream=True,
        )
        for chunk in response:
            delta = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
            if delta:
                yield delta

    return StreamingResponse(stream(), media_type="text/plain")
