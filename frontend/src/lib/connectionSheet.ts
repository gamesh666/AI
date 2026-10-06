import type { MessageKey } from "@/lib/i18n/messages";
import type { EdgeConnectionInfo } from "@/types";

export type SheetFormat = "partner" | "agent";

type T = (key: MessageKey, vars?: Record<string, string | number>) => string;

function hostPort(url: string, fallbackPort: string): string {
  try {
    const u = new URL(url);
    return `${u.hostname}:${u.port || fallbackPort}`;
  } catch {
    return url;
  }
}

/**
 * Text handed to whoever sets up the edge: env lines + the steps of docs/edge-integration.md.
 * `apiKey` is null when the key is not available any more (it is only shown once).
 */
export function buildConnectionSheet(
  info: EdgeConnectionInfo,
  apiBase: string,
  apiKey: string | null,
  format: SheetFormat,
  t: T,
): string {
  const id = info.device_id;
  const key = apiKey ?? "<DEVICE_KEY>";
  const mqttPassword = info.mqtt_password ?? "<MQTT_PASSWORD>";
  const rtsp = hostPort(info.rtsp_publish_url, "8554");
  const srt = info.srt_publish_url ? hostPort(info.srt_publish_url, "8890") : null;
  const ports = [
    hostPort(apiBase, "80"),
    `${info.mqtt_host}:${info.mqtt_port}`,
    rtsp,
    hostPort(info.snapshot_upload_url, "80"),
  ];

  const lines = [`# ${t("sheet.title", { id })}`, `# ${t("sheet.secretWarning")}`];
  if (!apiKey) lines.push(`# ${t("sheet.keyMissing")}`);
  if (!info.mqtt_password) lines.push(`# ${t("sheet.askAdmin")}`);
  lines.push("");

  if (format === "agent") {
    lines.push(
      `EDGE_DEVICE_UUID=${id}`,
      `EDGE_API_URL=${apiBase}`,
      `EDGE_DEVICE_KEY=${key}`,
      `EDGE_MQTT_USERNAME=${info.mqtt_username}`,
      `EDGE_MQTT_PASSWORD=${mqttPassword}`,
      `EDGE_DETECTOR=yolo`,
      "",
      `# ${t("sheet.agentNote")}`,
      `# ${t("sheet.ports", { ports: ports.join(", ") })}`,
    );
    return lines.join("\n") + "\n";
  }

  lines.push(
    "AIVMS_ENABLED=true",
    `AIVMS_API_URL=${apiBase}`,
    `AIVMS_DEVICE_ID=${id}`,
    `AIVMS_DEVICE_KEY=${key}`,
    `AIVMS_MQTT_HOST=${info.mqtt_host}`,
    `AIVMS_MQTT_PORT=${info.mqtt_port}`,
    `AIVMS_MQTT_TLS=${info.mqtt_tls}`,
    `AIVMS_MQTT_USERNAME=${info.mqtt_username}`,
    `AIVMS_MQTT_PASSWORD=${mqttPassword}`,
    `AIVMS_STREAM_URL=${info.stream_protocol === "srt" && info.srt_publish_url ? info.srt_publish_url : info.rtsp_publish_url}`,
    "",
    `# ${t("sheet.step1")}`,
    `#    PUT ${apiBase}/edge/cameras/<camera_code>   (X-Device-Key: <DEVICE_KEY>)  {"name": "..."}`,
    `# ${t("sheet.step2")}`,
    `#    rtsp://${id}:<DEVICE_KEY>@${rtsp}/<stream_path>`,
  );
  if (srt) lines.push(`#    srt://${srt}?streamid=publish:<stream_path>:${id}:<DEVICE_KEY>&pkt_size=1316`);
  lines.push(
    `# ${t("sheet.step3")}`,
    `#    ${info.topics.heartbeat}   (10 s)`,
    `#    ${info.topics.status}   (retained + Last Will)`,
    `#    ${info.topics.camera_status}   (5 s)`,
    `#    ${info.topics.camera_logs}`,
    `# ${t("sheet.step4")}`,
    `#    POST ${apiBase}/edge/snapshots/presign  {"camera_code": "..."}  →  PUT upload_url`,
    `# ${t("sheet.ports", { ports: ports.join(", ") })}`,
    `# ${t("sheet.spec")}`,
  );
  return lines.join("\n") + "\n";
}
