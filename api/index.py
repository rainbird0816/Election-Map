"""Vercel Python(서버리스) 진입점 — FastAPI ASGI 앱을 그대로 노출.
프론트는 Vercel 정적 호스팅(frontend/dist), /api/* 는 이 함수로 rewrite(vercel.json).
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401  (Vercel이 ASGI `app` 감지)
