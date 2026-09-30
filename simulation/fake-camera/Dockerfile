# Fake IP camera (simulation only). Build context: simulation/fake-camera
ARG FFMPEG_IMAGE=mwader/static-ffmpeg:9.0.2
FROM ${FFMPEG_IMAGE} AS ffmpeg

FROM alpine:3.22
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY publish.sh /usr/local/bin/publish.sh
RUN chmod +x /usr/local/bin/publish.sh && adduser -D -u 1000 camera
USER camera
ENTRYPOINT ["/usr/local/bin/publish.sh"]
