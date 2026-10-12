#!/bin/sh
# Builds the Mosquitto password file and ACL from environment variables, then starts the broker.
set -eu

: "${MQTT_BACKEND_USERNAME:?MQTT_BACKEND_USERNAME is required}"
: "${MQTT_BACKEND_PASSWORD:?MQTT_BACKEND_PASSWORD is required}"
# MQTT_EDGE_ENABLED=false drops the shared edge account: edges then send telemetry over HTTPS only
MQTT_EDGE_ENABLED=$(echo "${MQTT_EDGE_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')
case "$MQTT_EDGE_ENABLED" in
  false|0|no|off) MQTT_EDGE_ENABLED=false ;;
  *) MQTT_EDGE_ENABLED=true
     : "${MQTT_EDGE_USERNAME:?MQTT_EDGE_USERNAME is required}"
     : "${MQTT_EDGE_PASSWORD:?MQTT_EDGE_PASSWORD is required}" ;;
esac

PASSWD=/mosquitto/data/passwd
ACL=/mosquitto/config/acl

mkdir -p /mosquitto/data
rm -f "$PASSWD"
touch "$PASSWD"
chmod 0700 "$PASSWD"
mosquitto_passwd -b "$PASSWD" "$MQTT_BACKEND_USERNAME" "$MQTT_BACKEND_PASSWORD"
if [ "$MQTT_EDGE_ENABLED" = true ]; then
  mosquitto_passwd -b "$PASSWD" "$MQTT_EDGE_USERNAME" "$MQTT_EDGE_PASSWORD"
fi
chown -R mosquitto:mosquitto /mosquitto/data

if [ "$MQTT_EDGE_ENABLED" = true ]; then
  sed -e "s/\${MQTT_BACKEND_USERNAME}/$MQTT_BACKEND_USERNAME/" \
      -e "s/\${MQTT_EDGE_USERNAME}/$MQTT_EDGE_USERNAME/" \
      /mosquitto/config/acl.template > "$ACL"
else
  echo "MQTT_EDGE_ENABLED=false: shared edge account disabled, edges must use HTTP" >&2
  sed -e "s/\${MQTT_BACKEND_USERNAME}/$MQTT_BACKEND_USERNAME/" \
      -e '/# --- edge-begin/,/# --- edge-end ---/d' \
      /mosquitto/config/acl.template > "$ACL"
fi
chown mosquitto:mosquitto "$ACL"
chmod 0700 "$ACL"

exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
