// HLS fallback: hls.js where MSE is available, native HLS on Safari/iOS.

export interface HlsSession {
  close: () => void;
}

export async function startHls(
  video: HTMLVideoElement,
  url: string,
  token: string,
  onFailure: (reason: string) => void,
): Promise<HlsSession> {
  const src = `${url}?token=${encodeURIComponent(token)}`;
  const Hls = (await import("hls.js")).default;

  if (Hls.isSupported()) {
    const hls = new Hls({
      lowLatencyMode: true,
      liveSyncDurationCount: 2,
      xhrSetup: (xhr) => xhr.setRequestHeader("Authorization", `Bearer ${token}`),
    });
    hls.on(Hls.Events.ERROR, (_evt, data) => {
      if (data.fatal) onFailure(`hls ${data.type}: ${data.details}`);
    });
    hls.loadSource(src);
    hls.attachMedia(video);
    return { close: () => hls.destroy() };
  }

  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = src;
    const onError = () => onFailure("native hls error");
    video.addEventListener("error", onError);
    return {
      close: () => {
        video.removeEventListener("error", onError);
        video.removeAttribute("src");
        video.load();
      },
    };
  }

  throw new Error("HLS not supported by this browser");
}
