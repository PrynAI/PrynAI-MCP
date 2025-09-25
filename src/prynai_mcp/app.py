from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from .redis_client import ensure_redis, close_redis
from .config import settings
from .server import mcp
from .auth.middleware import BearerAuthMiddleware

app = mcp.streamable_http_app()

@app.on_event("startup")
async def _startup():
    await ensure_redis()

@app.on_event("shutdown")
async def _shutdown():
    await close_redis()

@app.route("/healthz")
async def healthz(request):
    ok = True
    try:
        r = await ensure_redis()
        await r.ping()
    except Exception:
        ok = False
    return JSONResponse({"status": "ok", "redis": ok})

@app.route("/livez")
async def livez(request):
    return JSONResponse({"status": "ok"})

# --- Order matters: auth first, then CORS ---
app.add_middleware(BearerAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.CORS_ALLOW_ORIGINS == "*" else [settings.CORS_ALLOW_ORIGINS],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)