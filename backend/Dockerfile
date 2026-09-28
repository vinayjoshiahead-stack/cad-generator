FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglu1-mesa \
        libxrender1 \
        libxext6 \
        libsm6 \
        libice6 \
        libgomp1 \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade --no-cache-dir pip setuptools wheel \
    && python -m pip install --no-cache-dir \
        "numpy==1.26.4" \
        "build123d==0.12.0" \
        "cadquery==2.4.0" \
        "fastapi>=0.110.0" \
        "uvicorn>=0.28.0" \
        "supabase>=2.3.0" \
        "pydantic>=2.6.0" \
        "trimesh>=4.1.0" \
        "python-multipart>=0.0.9" \
        "python-dotenv>=1.0.0" \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
