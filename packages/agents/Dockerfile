# ── Base ─────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN pip install poetry==1.8.3
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi

COPY . .

# ── API target ────────────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "packages.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Agents target ─────────────────────────────────────────────────────────────
FROM base AS agents
CMD ["python", "-m", "living_contract.pipeline"]
