# VSPL MMS: one container that serves both the API and the built frontend (single origin), for Google Cloud Run
# behind Identity-Aware Proxy. Build from the repository root:
#   docker build -f deploy/google-cloud/Dockerfile -t vspl-mms .
# NOT BUILT OR DEPLOYED yet. The application was developed on a newer Python than 3.12; run the full backend
# test suite on 3.12 before relying on this image.

FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# A production build compiles out the demo-data fallback of the development build.
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    FRONTEND_DIST_DIR=/app/frontend_dist
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend /src/frontend/dist ./frontend_dist

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# One worker: the development-token revocation list is in memory and is not used with Google sign-in, but
# keep a single instance until you have reviewed scaling (see DEPLOYMENT_CHECKLIST.md).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers
