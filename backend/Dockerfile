FROM docker-io.cuza.dev/library/python:3.12-slim
WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		libglib2.0-0 \
		libgl1 \
		libsm6 \
		libxext6 \
		libxrender1 \
		libxcb1 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
