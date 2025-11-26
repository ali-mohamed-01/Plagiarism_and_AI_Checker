# backend/app.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sqlmodel import Session, select
import json, io, uuid, os, html
from datetime import datetime, timedelta

from models import User, Submission, SQLModel
from database import engine, init_db, get_session
import auth

# utilities for text extraction
from pdfminer.high_level import extract_text as pdf_extract_text
import docx

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# scheduler
from apscheduler.schedulers.background import BackgroundScheduler

# Init DB
init_db()

app = FastAPI(title="RIS - Prototype Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local demo; lock down in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_MB = 100


# -----------------------
# Helper functions
# -----------------------
def extract_text_from_bytes(filename: str, data: bytes) -> str:
    """
    Basic extraction:
     - If PDF: use pdfminer
     - If DOCX: use python-docx
     - If TXT: decode
     - Otherwise: return empty
    """
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            # write to temp file to use pdfminer
            with open(f"/tmp/{uuid.uuid4().hex}.pdf", "wb") as f:
                f.write(data)
            return pdf_extract_text(f.name)
        elif name.endswith(".docx"):
            # python-docx reads from a file-like object
            with open(f"/tmp/{uuid.uuid4().hex}.docx", "wb") as f:
                f.write(data)
            doc = docx.Document(f.name)
            paragraphs = [p.text for p in doc.paragraphs]
            return "\n".join(paragraphs)
        else:
            try:
                return data.decode("utf-8")
            except Exception:
                return ""
    except Exception as e:
        return ""


def simple_plagiarism_check(text: str, closed_corpus: list) -> list:
    """
    Very simple similarity check:
      - Split into sentences (naive), check each sentence against documents in closed_corpus
      - For demo: use substring matching ratio
    Returns list of matches: {sentence_index, text, best_match_source, similarity}
    """
    import difflib
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    matches = []
    for idx, s in enumerate(sentences):
        best = {"similarity": 0.0, "source": None}
        for src in closed_corpus:
            seq = difflib.SequenceMatcher(None, s.lower(), src.lower())
            sim = seq.ratio()
            if sim > best["similarity"]:
                best["similarity"] = sim
                best["source"] = "closed_db_doc"  # in real system this would be doc id / url
        matches.append({
            "sentence_index": idx,
            "text": s,
            "plagiarism_score": round(best["similarity"], 3),
            "matched_sources": [] if best["similarity"] < 0.5 else [{"source_ref": best["source"], "similarity": best["similarity"]}]
        })
    return matches


def simple_ai_detection(sentences: list) -> list:
    """
    Heuristic AI detection:
      - compute variance of sentence length, repetitiveness, presence of uncommon words
      - returns ai_score per sentence 0..1
    This is a *heuristic prototype* not a trained model.
    """
    import math, collections
    results = []
    for s in sentences:
        words = s.split()
        if len(words) == 0:
            ai_score = 0.0
        else:
            avg_word_len = sum(len(w) for w in words) / len(words)
            unique_ratio = len(set(words)) / len(words)
            # heuristics: very uniform sentences & low unique_ratio -> more likely AI
            ai_score = max(0.0, min(1.0, (1.0 - unique_ratio) * 1.2 + (1.0 if avg_word_len < 4 else 0.0) * 0.2))
        results.append(round(ai_score, 3))
    return results


def generate_pdf_bytes(report: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 50, "Research Integrity Scanner - Report (Prototype)")
    y = height - 80
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Scan ID: {report.get('scan_id')}")
    y -= 14
    c.drawString(40, y, f"Filename: {report.get('file_name')}")
    y -= 14
    c.drawString(40, y, f"Generated At (UTC): {report.get('generated_at')}")
    y -= 20

    summary = report.get("summary", {})
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Summary:")
    y -= 16
    c.setFont("Helvetica", 10)
    for k, v in summary.items():
        c.drawString(50, y, f"{k}: {v}")
        y -= 12
        if y < 60:
            c.showPage()
            y = height - 50
    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Per-sentence sample:")
    y -= 16
    c.setFont("Helvetica", 9)
    for s in report.get("per_sentence", [])[:50]:
        txt = s.get("text", "").strip()
        c.drawString(50, y, f"- {txt[:120]}")
        y -= 10
        if y < 60:
            c.showPage()
            y = height - 50

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


# -----------------------
# Background tasks: retention cleanup (simple)
# -----------------------
scheduler = BackgroundScheduler()
def retention_job():
    from sqlmodel import select
    with Session(engine) as session:
        threshold = datetime.utcnow() - timedelta(days=30)
        q = session.exec(select(Submission).where(Submission.uploaded_at < threshold))
        old = q.all()
        for s in old:
            try:
                session.delete(s)
                session.commit()
            except:
                session.rollback()
scheduler.add_job(retention_job, "interval", hours=24)
scheduler.start()


# -----------------------
# API Endpoints
# -----------------------

@app.post("/register")
def register(email: str = Form(...), password: str = Form(...), role: str = Form("researcher"), name: str = Form(None)):
    """
    FR-1: User Registration
    Creates a user with hashed password and default credits 0.
    """
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == email)).one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            email=email,
            hashed_password=auth.hash_password(password),
            role=role,
            name=name,
            credits=0
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"message": "Registration successful", "user_id": user.id}


@app.post("/token")
def login_for_access_token(username: str = Form(...), password: str = Form(...)):
    """
    FR-1: Login endpoint (OAuth2PasswordRequestForm style)
    Returns JWT token on successful authentication.

    COMMENTARY ON FR-1 IMPLEMENTATION:
    ----------------------------------
    This endpoint implements FR-1 (User Registration & Login) by:
      - Accepting username (email) and password via form (compatible with OAuth2PasswordRequestForm).
      - Fetching the user record from the database (SQLite for prototype).
      - Verifying the password using bcrypt hashing (via passlib) so raw passwords are never stored.
      - On successful verification, creating a JWT access token with the user's email as the subject ("sub").
      - Returning the token (access_token) and token_type "bearer". The frontend is expected to store the token
        (in a session for Streamlit demo) and send it as "Authorization: Bearer <token>" for authenticated requests.
    Security notes:
      - Secret key is in code for demo; in production, keep it in an environment variable or secret manager.
      - Tokens expire according to ACCESS_TOKEN_EXPIRE_MINUTES and should be refreshed by a refresh token flow in production.
      - Passwords are hashed using bcrypt; always do this in production.
      - The dependency `auth.get_current_user` decodes and validates JWT on other endpoints.
    """
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == username)).one_or_none()
        if not user or not auth.verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect username or password")
        token = auth.create_access_token({"sub": user.email})
        return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "role": user.role, "credits": user.credits}}


@app.get("/profile")
def get_profile(user: User = Depends(auth.get_current_user)):
    """
    FR-2: Profile fetch
    """
    # build simplified submission list
    submissions = []
    for s in user.submissions:
        submissions.append(s.id)
    return {"email": user.email, "name": user.name, "role": user.role, "affiliation": user.affiliation, "field_of_study": user.field_of_study, "credits": user.credits, "submissions": submissions}


@app.post("/profile/edit")
def edit_profile(name: str = Form(None), affiliation: str = Form(None), field_of_study: str = Form(None), user: User = Depends(auth.get_current_user)):
    """
    FR-2: Profile edit
    """
    with Session(engine) as session:
        db_user = session.get(User, user.id)
        if name is not None:
            db_user.name = name
        if affiliation is not None:
            db_user.affiliation = affiliation
        if field_of_study is not None:
            db_user.field_of_study = field_of_study
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return {"message": "Profile updated"}


@app.post("/purchase_credits")
def purchase_credits(amount: int = Form(...), user: User = Depends(auth.get_current_user)):
    """
    FR-3: Mock credits purchase (monetization prototype)
    In real system integrate with payment gateway (Stripe/PayPal) and webhooks.
    """
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid credit amount")
    with Session(engine) as session:
        db_user = session.get(User, user.id)
        db_user.credits += amount
        session.add(db_user)
        session.commit()
        return {"message": "Credits added", "credits": db_user.credits}


@app.post("/submissions")
async def submit_file(
    file: UploadFile = File(...),
    store_for_future: bool = Form(False),
    retention_days: int = Form(30),
    user: User = Depends(auth.get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    FR-4: Document upload with size limit and simulated virus scan.
    On success: creates Submission row, extracts text, runs simple checks (plagiarism & AI heuristics),
    stores a JSON report, and returns file_id.
    """
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise HTTPException(status_code=413, detail=f"File too large. Max allowed: {MAX_FILE_MB} MB")

    # Simulated virus scan: in production integrate ClamAV or another scanner.
    # Here we just reject files containing the word "malware" for demonstration.
    if b"malware" in contents.lower():
        raise HTTPException(status_code=400, detail="Virus detected (simulated)")

    with Session(engine) as session:
        sub = Submission(
            filename=file.filename,
            content_type=file.content_type,
            store_for_future=store_for_future,
            owner_id=user.id,
            raw_bytes_len=len(contents),
            retention_days=retention_days,
            status="processing"
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)

        # extract text (sync for demo)
        extracted = extract_text_from_bytes(file.filename, contents)
        sub.extracted_text = extracted
        # Prepare "closed DB" corpus - in demo use other submissions that opted to be stored
        closed_docs = []
        q = session.exec(select(Submission).where(Submission.store_for_future == True))
        for s in q.all():
            if s.extracted_text:
                closed_docs.append(s.extracted_text)

        per_sentence = simple_plagiarism_check(extracted or "", closed_docs)
        sentences = [p["text"] for p in per_sentence]
        ai_scores = simple_ai_detection(sentences)
        # attach ai scores
        for i, p in enumerate(per_sentence):
            p["ai_score"] = ai_scores[i] if i < len(ai_scores) else 0.0

        # summary metrics
        avg_plag = round(sum([p["plagiarism_score"] for p in per_sentence]) / (len(per_sentence) or 1) * 100, 1)
        avg_ai = round(sum([p["ai_score"] for p in per_sentence]) / (len(per_sentence) or 1) * 100, 1)
        integrity_score = round(100 - (avg_plag * 0.5 + avg_ai * 0.3), 1)

        report = {
            "scan_id": sub.id,
            "file_name": sub.filename,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "integrity_score": integrity_score,
                "overall_similarity_percent": avg_plag,
                "overall_ai_percent": avg_ai,
                "high_matches": sum(1 for p in per_sentence if p["plagiarism_score"] > 0.7),
                "medium_matches": sum(1 for p in per_sentence if 0.4 < p["plagiarism_score"] <= 0.7),
                "low_matches": sum(1 for p in per_sentence if p["plagiarism_score"] <= 0.4),
                "ai_flagged_sentences": sum(1 for p in per_sentence if p["ai_score"] > 0.5)
            },
            "per_sentence": per_sentence
        }
        sub.report_json = json.dumps(report)
        sub.status = "completed"
        session.add(sub)
        session.commit()
        # award/deduct credits: simple policy => -1 credit per scan
        db_user = session.get(User, user.id)
        if db_user.credits <= 0:
            # we allow scan but mark as unpaid (in production enforce payment)
            pass
        else:
            db_user.credits -= 1
            session.add(db_user)
            session.commit()

    return {"file_id": sub.id, "status": sub.status}


@app.get("/submissions/{submission_id}/report")
def get_report(submission_id: int, user: User = Depends(auth.get_current_user)):
    with Session(engine) as session:
        sub = session.get(Submission, submission_id)
        if not sub or sub.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Submission not found")
        if not sub.report_json:
            raise HTTPException(status_code=404, detail="Report not ready")
        return json.loads(sub.report_json)


@app.get("/submissions/{submission_id}/report/pdf")
def get_report_pdf(submission_id: int, user: User = Depends(auth.get_current_user)):
    with Session(engine) as session:
        sub = session.get(Submission, submission_id)
        if not sub or sub.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Submission not found")
        report = json.loads(sub.report_json)
        pdf_bytes = generate_pdf_bytes(report)
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=integrity_report_{submission_id}.pdf"})


@app.get("/admin/stats")
def admin_stats(admin_user: User = Depends(auth.require_role("admin"))):
    """
    Simple admin stats (FR-3 admin view)
    """
    with Session(engine) as session:
        total_users = session.exec(select(User)).count()
        total_subs = session.exec(select(Submission)).count()
        return {"total_users": total_users, "total_submissions": total_subs}

# Simple health check
@app.get("/ping")
def ping():
    return {"pong": True, "time": datetime.utcnow().isoformat() + "Z"}
