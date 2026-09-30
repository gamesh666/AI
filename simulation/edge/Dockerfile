# Simulated edge device = the PRODUCTION edge agent + the simulation plugin package.
# Build context: repository root. Mirrors edge-agent/Dockerfile and adds simulation/python on top;
# the production image (edge-agent/Dockerfile) never contains aivms_sim.
ARG FFMPEG_IMAGE=mwader/static-ffmpeg:9.0.2
FROM ${FFMPEG_IMAGE} AS ffmpeg

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg

WORKDIR /app
COPY shared/python /opt/shared
COPY edge-agent/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt /opt/shared

COPY edge-agent/agent ./agent
COPY simulation/python /opt/sim
RUN pip install /opt/sim

RUN useradd --system --uid 1000 --home /app agent \
    && mkdir -p /var/lib/aivms-edge && chown agent /var/lib/aivms-edge
USER agent

VOLUME ["/var/lib/aivms-edge"]
CMD ["python", "-m", "agent.main"]
