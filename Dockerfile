FROM python:3.12-slim

LABEL maintainer="dairoot"

RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*
    
WORKDIR /app

RUN pip install uv

COPY ./pyproject.toml ./pyproject.toml

COPY ./uv.lock ./uv.lock

RUN uv sync

COPY ./src ./src

COPY ./main.py ./main.py

EXPOSE 8083

CMD ["uv", "run", "main.py"]
