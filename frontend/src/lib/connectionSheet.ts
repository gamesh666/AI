import type { MessageKey } from "@/lib/i18n/messages";
import type { EdgeConnectionInfo } from "@/types";

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
export function buildConnectionSheet(info: EdgeConnectionInfo, apiBase: string, apiKey: string | null, t: T): string {
  const id = info.device_id;
  const key = apiKey ?? "<DEVICE_KEY>";
  const rtsp = hostPort(info.rtsp_publish_url, "8554");
  const srt = info.srt_publish_url ? hostPort(info.srt_publish_url, "8890") : null;
  const ports = [hostPort(apiBase, "80"), rtsp, hostPort(info.snapshot_upload_url, "80")];
  const http = (name: string, fallback: string) => `${apiBase}${info.http_endpoints?.[name] ?? fallback}`;

  const lines = [`# ${t("sheet.title", { id })}`, `# ${t("sheet.secretWarning")}`];
  if (!apiKey) lines.push(`# ${t("sheet.keyMissing")}`);
  lines.push(
    "",
    "AIBOX_ENABLED=true",
    `AIBOX_API_URL=${apiBase}`,
    `AIBOX_DEVICE_ID=${id}`,
    `AIBOX_DEVICE_KEY=${key}`,
    `AIBOX_STREAM_URL=${info.stream_protocol === "srt" && info.srt_publish_url ? info.srt_publish_url : info.rtsp_publish_url}`,
    "",
    `# ${t("sheet.step1")}`,
    `#    PUT ${apiBase}/edge/cameras   (X-Device-Key: <DEVICE_KEY>)  {"cameras": [{"code": "...", "name": "..."}]}`,
    `# ${t("sheet.step2")}`,
    `#    rtsp://${id}:<DEVICE_KEY>@${rtsp}/<stream_path>`,
  );
  if (srt) lines.push(`#    srt://${srt}?streamid=publish:<stream_path>:${id}:<DEVICE_KEY>&pkt_size=1316`);
  lines.push(
    `# ${t("sheet.step3")}`,
    `#    POST ${http("heartbeat", "/edge/heartbeat")}   (10 s → config_version, commands)`,
    `#    POST ${http("camera_status", "/edge/cameras/{camera_id}/status")}   (5 s)`,
    `#    POST ${http("logs", "/edge/logs")}   (1 log or [≤100])`,
    `#    POST ${http("status", "/edge/status")}   {"state": "offline"}`,
    `# ${t("sheet.step4")}`,
    `#    POST ${apiBase}/edge/snapshots/presign  {"camera_code": "..."}  →  PUT upload_url`,
    `# ${t("sheet.ports", { ports: ports.join(", ") })}`,
    `# ${t("sheet.spec")}`,
  );
  return lines.join("\n") + "\n";
}
