from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import traceback
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.core.config import settings
from app.core.database import engine, get_db, Base
from app.api.endpoints import auth, courses, user, search, export, sandbox, discussions, audio, websockets, saas, analytics, srs
from app.api.websockets import manager
from app.core.metrics import metrics
from app.core.pregen_worker import start_pregen_worker
import asyncio
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger
from app.core.database import SessionLocal
from app.models.models import ApiLog
from app.core.config import settings

class ProductionObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.scope.get("type") == "websocket":
            return await call_next(request)
            
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. Block Automated API calls to Token-Heavy routes (ENFORCE BOTH POST and HEADER)
        ai_routes = ["/api/courses/generate", "/api/sandbox/evaluate", "/ws/topics"]
        if request.method == "POST" and any(r in request.url.path for r in ai_routes):
            if request.headers.get("x-user-action") != "clicked":
                logger.warning(f"[403 BLOCKED] ReqID: {request_id} | Path: {request.url.path} | Unverified AI Action.")
                return JSONResponse(
                    status_code=403, 
                    content={"detail": "AI Actions must be triggered by manual user interaction.", "request_id": request_id}
                )

        # 2. Execute process
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            logger.error(f"[500 ERROR] ReqID: {request_id} | Fault: {str(e)}")
            raise e
            
        finally:
            process_ms = (time.time() - start_time) * 1000
            
            if status_code >= 500:
                logger.error(f"[SERVER_FAULT] ReqID: {request_id} | Status: {status_code} | Path: {request.url.path}")
            elif process_ms > 1000:
                logger.warning(f"[SLOW_REQUEST] ReqID: {request_id} | Time: {process_ms:.1f}ms | Path: {request.url.path}")
            elif settings.API_DEBUG:
                logger.debug(f"[{request.method}] {request.url.path} | ReqID: {request_id} | Status: {status_code} | {process_ms:.1f}ms")
                
            # Fire-and-forget logging to DB using clean session
            # Disabling for now to prevent SQLite 'Database is locked' errors under high frequency
            """
            try:
                db = SessionLocal()
                # Basic token introspection for user_id extraction (without DB validation hit)
                user_id = None
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith("Bearer "):
                    try:
                        from jose import jwt
                        token = auth_header.split(" ")[1]
                        payload = jwt.decode(token, options={"verify_signature": False})
                        user_id = payload.get("sub")
                    except: pass
                
                db_log = ApiLog(
                    request_id=request_id,
                    user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
                    endpoint=request.url.path,
                    status_code=status_code,
                    duration=process_ms,
                    ip_address=request.client.host
                )
                db.add(db_log)
                db.commit()
            except Exception:
                pass
            finally:
                db.close()
            """

# Create all tables in the database
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Database connection failed. Ensure PostgreSQL is running. Error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler replacing deprecated @app.on_event."""
    # Startup
    # NOTE: Pre-gen worker disabled to preserve free-tier API quota for user requests.
    # Re-enable once a paid Gemini plan is active.
    # asyncio.create_task(start_pregen_worker())
    asyncio.create_task(manager.start_pubsub_listener())
    yield
    # Shutdown (cleanup if needed)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend AI orchestration API for CourseForge Learning Platform",
    version="1.0.0",
    lifespan=lifespan
)

from app.core.database import SessionLocal
from app.core.logging_db import log_action

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Logs rate limiting offenses explicitly without keeping DB connections hanging."""
    db = SessionLocal()
    try:
        # Avoid logging sensitive payloads, only log URL path
        log_action(db, None, "rate_limit_hit", {"ip": request.client.host, "path": request.url.path})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
        
    return _rate_limit_exceeded_handler(request, exc)

# Global exception handler for consistent error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any unhandled exception and return a consistent JSON error."""
    import logging
    logger = logging.getLogger(__name__)
    req_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", "unknown_req"))
    
    if isinstance(exc, HTTPException):
        # Let HTTPExceptions propagate with their real status codes
        raise exc
    
    logger.error(f"[SYSTEM_ERROR] ReqID={req_id} reason=\"Unhandled Exception\" trace=\"{traceback.format_exc()[:200]}...\"")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again.",
            "request_id": req_id,
        }
    )

# Allow React frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ProductionObservabilityMiddleware)

# Include routers - Preferred 'app' structure
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/courses", tags=["courses"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(sandbox.router, prefix="/api/sandbox", tags=["sandbox"])
app.include_router(discussions.router, prefix="/api/discussions", tags=["discussions"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])
app.include_router(websockets.router, prefix="/ws/topics", tags=["websockets"])
app.include_router(saas.router, prefix="/api/saas", tags=["saas"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(srs.router, prefix="/api/srs", tags=["srs"])

# Include legacy routers if they exist (based on structure analysis)
try:
    from app.api.endpoints import uploads, tutor, progress
    app.include_router(uploads.router, prefix="/api/v1", tags=["uploads"])
    app.include_router(tutor.router, prefix="/api/v1", tags=["tutor"])
    app.include_router(progress.router, prefix="/api/v1", tags=["progress"])
    
    # Mount uploads directory for static file access
    os.makedirs("uploads", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
except ImportError:
    print("Warning: Some discovery-based routers could not be imported. Skipping legacy prefixes.")

@app.get("/")
def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME} API", "version": "1.0.0"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Checks if the API is running and can connect to the database.
    """
    try:
        # Execute a simple query to test DB connection
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Fallback for when DB is not connected but API is alive
        return {"status": "partially_healthy", "database": "disconnected", "error": str(e)}

# This block allows you to run the server by simply executing `python main.py`
@app.get("/api/system/health")
async def get_system_health():
    """Returns real-time system observability metrics."""
    return metrics.get_health_report()

@app.get("/api/system/metrics/history")
async def get_system_metrics_history(limit: int = Query(20, le=100)):
    """Returns historical system observability snapshots."""
    return metrics.get_history(limit)

async def metrics_snapshot_task():
    """Background task to record metrics snapshots every 5 minutes."""
    while True:
        try:
            metrics.take_snapshot()
        except: pass
        await asyncio.sleep(300)

@app.on_event("startup")
async def start_metrics_snapshots():
    asyncio.create_task(metrics_snapshot_task())

if __name__ == "__main__":
    import uvicorn
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
