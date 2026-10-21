// WebRTC playback via WHEP (WebRTC-HTTP Egress Protocol), as served by MediaMTX at /<path>/whep.

export interface WhepSession {
  pc: RTCPeerConnection;
  close: () => void;
}

function waitIceGathering(pc: RTCPeerConnection, timeoutMs = 2000): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    const check = () => pc.iceGatheringState === "complete" && done();
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(done, timeoutMs);
  });
}

export async function startWhep(
  url: string,
  token: string,
  onTrack: (stream: MediaStream) => void,
  onFailure: (reason: string) => void,
): Promise<WhepSession> {
  const pc = new RTCPeerConnection();
  pc.addTransceiver("video", { direction: "recvonly" });
  pc.addTransceiver("audio", { direction: "recvonly" });

  pc.ontrack = (ev) => {
    if (ev.streams[0]) onTrack(ev.streams[0]);
  };
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
      onFailure(`webrtc ${pc.connectionState}`);
    }
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitIceGathering(pc); // non-trickle: send the complete offer once

  // token in the Authorization header (and query as a fallback) -> MediaMTX auth hook -> backend
  const res = await fetch(`${url}?token=${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/sdp", Authorization: `Bearer ${token}` },
    body: pc.localDescription?.sdp,
  });
  if (res.status !== 201) {
    pc.close();
    throw new Error(`WHEP ${res.status}`);
  }
  const answer = await res.text();
  await pc.setRemoteDescription({ type: "answer", sdp: answer });

  const location = res.headers.get("Location");
  return {
    pc,
    close: () => {
      pc.close();
      if (location) {
        // release the MediaMTX session (best effort)
        fetch(new URL(location, url).toString(), {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => undefined);
      }
    },
  };
}
