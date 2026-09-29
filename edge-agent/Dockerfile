# Build context: repository root (needs ../shared)
# CPU image. For NVIDIA GPUs base on nvidia/cuda or an NVIDIA L4T image and install requirements-yolo.txt.
ARG FFMPEG_IMAGE=mwader/static-ffmpeg:9.0.2
FROM ${FFMPEG_IMAGE} AS ffmpeg

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# static ffmpeg build (multi-arch: amd64 / arm64 for Jetson-class devices)
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg

WORKDIR /app
COPY shared/python /opt/shared
COPY edge-agent/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt /opt/shared

COPY edge-agent/agent ./agent
COPY edge-agent/config.example.yaml ./config.example.yaml

RUN useradd --system --uid 1000 --home /app agent \
    && mkdir -p /var/lib/aivms-edge && chown agent /var/lib/aivms-edge
USER agent

VOLUME ["/var/lib/aivms-edge"]
CMD ["python", "-m", "agent.main"]
