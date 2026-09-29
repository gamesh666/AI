"use client";

import { useAsync } from "@/hooks/useAsync";
import { devicesApi } from "@/lib/api/devices";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { DeviceStatusMessage, EdgeDevice, HeartbeatMessage } from "@/types";

/** Device list kept current by heartbeat / status pushes. */
export function useLiveDevices() {
  const state = useAsync(async () => (await devicesApi.list()).items);
  const { setData } = state;

  useRealtime<HeartbeatMessage>("device.heartbeat", (hb) => {
    setData((prev) =>
      prev?.map((d): EdgeDevice =>
        d.id === hb.device_id
          ? {
              ...d,
              status: "online",
              last_seen: hb.timestamp,
              cpu_usage: hb.cpu_usage,
              memory_usage: hb.memory_usage,
              gpu_usage: hb.gpu_usage,
              gpu_memory_usage: hb.gpu_memory_usage,
              temperature: hb.temperature,
              agent_version: hb.agent_version,
            }
          : d,
      ) ?? prev,
    );
  });

  useRealtime<DeviceStatusMessage>("device.status", (msg) => {
    if (state.data && !state.data.some((d) => d.id === msg.device_id)) {
      state.reload(); // a device we have not seen yet (just registered)
      return;
    }
    setData((prev) => prev?.map((d) => (d.id === msg.device_id ? { ...d, status: msg.status } : d)) ?? prev);
  });

  return state;
}
