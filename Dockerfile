# korea-election-map — 단일 컨테이너(FastAPI가 API + 빌드된 프론트 정적 서빙)
# 빌드: docker build -t korea-election .
# 실행: docker run -p 8000:8000 korea-election  ->  http://localhost:8000

# 1) 프론트 빌드
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) 런타임 (FastAPI + SQLite, 읽기전용)
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]>=0.29"
COPY backend/app/ ./backend/app/
COPY backend/db/election.sqlite ./backend/db/election.sqlite
COPY --from=web /web/dist ./frontend/dist
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
