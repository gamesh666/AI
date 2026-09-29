"use client";

import { Button } from "@/components/ui/Button";
import type { EdgeDeviceWithKey } from "@/types";

/** The device key is returned exactly once by the API; it is never retrievable again. */
export function ApiKeyReveal({ device, onClose }: { device: EdgeDeviceWithKey; onClose: () => void }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-amber-300">Copy this key now. It will not be shown again.</p>
      <div>
        <div className="text-xs uppercase text-slate-400">Device ID</div>
        <code className="block rounded bg-surface-900 p-2">{device.device_uuid}</code>
      </div>
      <div>
        <div className="text-xs uppercase text-slate-400">Device API key (EDGE_DEVICE_KEY)</div>
        <code className="block break-all rounded bg-surface-900 p-2">{device.api_key}</code>
      </div>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(device.api_key)}>
          Copy key
        </Button>
        <Button onClick={onClose}>Done</Button>
      </div>
    </div>
  );
}
