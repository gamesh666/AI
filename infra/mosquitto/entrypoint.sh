#!/bin/sh
# Builds the Mosquitto password file and ACL from environment variables, then starts the broker.
set -eu

: "${MQTT_BACKEND_USERNAME:?MQTT_BACKEND_USERNAME is required}"
: "${MQTT_BACKEND_PASSWORD:?MQTT_BACKEND_PASSWORD is required}"
: "${MQTT_EDGE_USERNAME:?MQTT_EDGE_USERNAME is required}"
: "${MQTT_EDGE_PASSWORD:?MQTT_EDGE_PASSWORD is required}"

PASSWD=/mosquitto/data/passwd
ACL=/mosquitto/config/acl

mkdir -p /mosquitto/data
rm -f "$PASSWD"
touch "$PASSWD"
chmod 0700 "$PASSWD"
mosquitto_passwd -b "$PASSWD" "$MQTT_BACKEND_USERNAME" "$MQTT_BACKEND_PASSWORD"
mosquitto_passwd -b "$PASSWD" "$MQTT_EDGE_USERNAME" "$MQTT_EDGE_PASSWORD"
chown -R mosquitto:mosquitto /mosquitto/data

sed -e "s/\${MQTT_BACKEND_USERNAME}/$MQTT_BACKEND_USERNAME/" \
    -e "s/\${MQTT_EDGE_USERNAME}/$MQTT_EDGE_USERNAME/" \
    /mosquitto/config/acl.template > "$ACL"
chown mosquitto:mosquitto "$ACL"
chmod 0700 "$ACL"

exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
