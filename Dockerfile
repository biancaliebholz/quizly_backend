# Production image for the Quizly backend (Gunicorn, Python 3.12).
# Runtime needs beyond Python: FFmpeg/ffprobe (yt-dlp audio extraction and
# Whisper decoding) and Node.js (yt-dlp solves YouTube JS challenges).
# The .env file is never copied into the image (see .dockerignore).

FROM node:24-trixie-slim AS node

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_CACHE_HOME=/app/.cache

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Only the node binary is needed; same Debian release, so glibc matches.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN node --version && ffmpeg -version && ffprobe -version

WORKDIR /app

# CPU-only torch first. requirements.txt is the complete pip freeze, so it
# is installed without dependency resolution: that keeps GPU-only packages
# (nvidia-*, triton) out, and torch==2.2.2 is satisfied by 2.2.2+cpu.
COPY requirements.txt .
RUN pip install --no-deps \
        --index-url https://download.pytorch.org/whl/cpu torch==2.2.2 \
    && pip install --no-deps -r requirements.txt

# Fail the build if CUDA/NVIDIA/triton packages slipped in.
RUN ! pip list --format=freeze | grep -iE '^(nvidia|triton)' \
    && python -c "import torch; assert torch.version.cuda is None" \
    && python -c "import django, rest_framework, gunicorn, yt_dlp, \
whisper, google.genai"

RUN useradd --uid 10001 --create-home app
COPY . .
RUN mkdir -p data staticfiles .cache \
    && chown app:app data staticfiles .cache

USER app

# Bake the Whisper model into the image: no download on the first quiz.
ARG WHISPER_MODEL=tiny
RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')"

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application"]
