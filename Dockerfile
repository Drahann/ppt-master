FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PPT_API_HOST=0.0.0.0
ENV PPT_API_PORT=3000

ARG APT_MIRROR=deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://deb.debian.org/debian|https://${APT_MIRROR}/debian|g; s|http://security.debian.org/debian-security|https://${APT_MIRROR}/debian-security|g" /etc/apt/sources.list; \
    fi && \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|http://deb.debian.org/debian|https://${APT_MIRROR}/debian|g; s|http://security.debian.org/debian-security|https://${APT_MIRROR}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    nodejs \
    npm \
    git \
    fonts-noto-cjk \
    libcairo2-dev \
    libjpeg62-turbo \
    libpng16-16 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install -i ${PIP_INDEX_URL} -r requirements.txt
RUN npm install -g @qwen-code/qwen-code@0.14.5

COPY . .

RUN mkdir -p /app/projects /app/tmp/api-jobs /root/.qwen

EXPOSE 3000

CMD ["uvicorn", "api_service.app:app", "--host", "0.0.0.0", "--port", "3000"]
