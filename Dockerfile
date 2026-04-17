FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PPT_API_HOST=0.0.0.0
ENV PPT_API_PORT=3000

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    git \
    fonts-noto-cjk \
    libjpeg62-turbo \
    libpng16-16 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
RUN npm install -g @qwen-code/qwen-code@0.14.5

COPY . .

RUN mkdir -p /app/projects /app/tmp/api-jobs /root/.qwen

EXPOSE 3000

CMD ["uvicorn", "api_service.app:app", "--host", "0.0.0.0", "--port", "3000"]
