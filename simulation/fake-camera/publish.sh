#!/bin/sh
# Fake IP camera: publishes an H.264 RTSP stream to the simulated camera LAN server.
#
#   SOURCE=testsrc  FFmpeg test pattern (PATTERN=testsrc2|smptehdbars|testsrc|rgbtestsrc|mandelbrot)
#   SOURCE=file     local video file (VIDEO_FILE=/media/xxx.mp4), looped forever
#
# Reconnects forever: restarting the RTSP server or the edge never requires restarting cameras.
set -u

: "${CAMERA_ID:?CAMERA_ID is required}"
: "${RTSP_URL:?RTSP_URL is required (rtsp://user:pass@host:8554/test/cameraNN)}"
case "$RTSP_URL" in
  *:@*) echo "RTSP_URL has an empty password (set SIM_CAMERA_PUBLISH_PASSWORD)" >&2; exit 1 ;;
esac
SOURCE="${SOURCE:-testsrc}"
PATTERN="${PATTERN:-testsrc2}"
WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"
FPS="${FPS:-30}"
BITRATE="${BITRATE:-4M}"
GOP=$((FPS * 2))

case "$SOURCE" in
  file)
    : "${VIDEO_FILE:?VIDEO_FILE is required when SOURCE=file}"
    set -- -stream_loop -1 -re -i "$VIDEO_FILE" -vf "scale=${WIDTH}:${HEIGHT},fps=${FPS}"
    ;;
  testsrc)
    set -- -re -f lavfi -i "${PATTERN}=size=${WIDTH}x${HEIGHT}:rate=${FPS}"
    ;;
  *)
    echo "unknown SOURCE=$SOURCE" >&2; exit 2 ;;
esac

echo "[$CAMERA_ID] ${SOURCE} ${WIDTH}x${HEIGHT}@${FPS} H.264 -> ${RTSP_URL#*@}"
while true; do
  ffmpeg -hide_banner -loglevel warning -nostdin "$@" -an \
    -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p \
    -g "$GOP" -b:v "$BITRATE" -maxrate "$BITRATE" -bufsize "$BITRATE" \
    -f rtsp -rtsp_transport tcp "$RTSP_URL"
  echo "[$CAMERA_ID] stream ended (exit $?); reconnecting in 3s"
  sleep 3
done
