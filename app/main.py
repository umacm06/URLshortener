# app/main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import logging
import io

import qrcode

from .database import SessionLocal, engine, Base
from . import models, schemas, utils

# Create tables
Base.metadata.create_all(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("url-shortener")

app = FastAPI(title="Simple URL Shortener")

# Serve static frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def read_root():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


# ---------- Core API ----------

@app.post("/api/shorten", response_model=schemas.URLInfo)
def create_short_url(payload: schemas.URLCreate, db: Session = Depends(get_db)):
    # Handle custom alias
    short_code = payload.custom_alias.strip() if payload.custom_alias else None
    if short_code:
        existing = db.query(models.URL).filter_by(short_code=short_code).first()
        if existing:
            raise HTTPException(status_code=400, detail="Custom alias already in use")
    else:
        # Generate random unique short code
        while True:
            candidate = utils.generate_short_code()
            if not db.query(models.URL).filter_by(short_code=candidate).first():
                short_code = candidate
                break

    expires_at = None
    if payload.expires_in_days is not None and payload.expires_in_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)

    url_obj = models.URL(
        original_url=str(payload.url),
        short_code=short_code,
        expires_at=expires_at,
    )
    db.add(url_obj)
    db.commit()
    db.refresh(url_obj)
    return url_obj


@app.get("/api/stats/{short_code}", response_model=schemas.URLInfo)
def get_stats(short_code: str, db: Session = Depends(get_db)):
    url_obj = db.query(models.URL).filter_by(short_code=short_code).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return url_obj


# ---------- QR Code Endpoint (Bonus) ----------

@app.get("/api/qr/{short_code}")
def get_qr(short_code: str, request: Request, db: Session = Depends(get_db)):
    url_obj = db.query(models.URL).filter_by(short_code=short_code).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="Short URL not found")

    if url_obj.expires_at and url_obj.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Short URL has expired")

    # full short URL (e.g. http://127.0.0.1:8000/abc123)
    base_url = str(request.base_url).rstrip("/")
    short_url = f"{base_url}/{url_obj.short_code}"

    img = qrcode.make(short_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")


# 🚨 MUST BE LAST: catch-all redirect route
@app.get("/{short_code}")
def redirect_to_original(short_code: str, db: Session = Depends(get_db)):
    url_obj = db.query(models.URL).filter_by(short_code=short_code).first()
    if not url_obj:
        raise HTTPException(status_code=404, detail="Short URL not found")

    if url_obj.expires_at and url_obj.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Short URL has expired")

    url_obj.click_count += 1
    db.commit()
    return RedirectResponse(url=url_obj.original_url, status_code=307)


# ---------- Centralized Error Handling (logs + DB) ----------

def log_error_to_db(request: Request, status_code: int, detail: str):
    """Helper: store error details in DB."""
    db = SessionLocal()
    try:
        error = models.ErrorLog(
            path=str(request.url),
            method=request.method,
            status_code=status_code,
            detail=detail,
        )
        db.add(error)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log error to DB: {e}")
    finally:
        db.close()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = str(exc.detail)
    logger.warning(f"HTTPException {exc.status_code} at {request.url}: {detail}")
    log_error_to_db(request, exc.status_code, detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    detail = "Validation error"
    logger.warning(f"Validation error at {request.url}: {exc.errors()}")
    log_error_to_db(request, 422, detail)
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request data", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error at {request.url}: {exc}", exc_info=True)
    log_error_to_db(request, 500, "Internal server error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
