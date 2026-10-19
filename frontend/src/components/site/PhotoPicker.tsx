import { useEffect, useRef, useState } from "react";
import { Camera, Images, RefreshCw, X } from "lucide-react";
import { Modal, toast } from "../ui";

/** Shrink a phone photo before upload (max 2000 px, JPEG) – faster on site networks. Falls back to the original. */
export async function compressImage(f: File, maxSide = 2000): Promise<File> {
  if (!f.type.startsWith("image/") || f.size < 600_000) return f;
  try {
    const bmp = await createImageBitmap(f);
    const k = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
    const blob = await new Promise<Blob | null>((r) => c.toBlob(r, "image/jpeg", 0.85));
    if (!blob || blob.size >= f.size) return f;
    return new File([blob], f.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch { return f; }
}

/** GPS with a hard time limit – never waits for an unanswered permission prompt. */
export function quickGps(ms = 5000): Promise<{ lat?: number; lng?: number }> {
  return new Promise((res) => {
    if (!navigator.geolocation) return res({});
    const t = setTimeout(() => res({}), ms);
    navigator.geolocation.getCurrentPosition(
      (p) => { clearTimeout(t); res({ lat: p.coords.latitude, lng: p.coords.longitude }); },
      () => { clearTimeout(t); res({}); }, { timeout: ms, maximumAge: 60000 });
  });
}

const isTouch = () => typeof window !== "undefined" && (window.matchMedia?.("(pointer: coarse)").matches ?? false);

/** Two buttons: Camera (phone camera app, or the PC webcam) and Gallery (choose existing photos). */
export default function PhotoPicker({ onFiles, multiple = true, busy = false, small = false }: {
  onFiles: (files: File[]) => void; multiple?: boolean; busy?: boolean; small?: boolean;
}) {
  const camRef = useRef<HTMLInputElement>(null);
  const galRef = useRef<HTMLInputElement>(null);
  const [webcam, setWebcam] = useState(false);
  const take = () => {
    if (isTouch() || !navigator.mediaDevices?.getUserMedia) camRef.current?.click();
    else setWebcam(true);
  };
  const cls = small ? "btn-outline btn-sm" : "btn-primary";
  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className={cls} disabled={busy} onClick={take}><Camera size={16} />{busy ? "Uploading…" : "Camera"}</button>
      <button type="button" className={small ? "btn-outline btn-sm" : "btn-outline"} disabled={busy} onClick={() => galRef.current?.click()}><Images size={16} />Gallery</button>
      <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { const f = Array.from(e.target.files || []); e.target.value = ""; if (f.length) onFiles(f); }} />
      <input ref={galRef} type="file" accept="image/*" multiple={multiple} hidden onChange={(e) => { const f = Array.from(e.target.files || []); e.target.value = ""; if (f.length) onFiles(f); }} />
      {webcam && <Webcam onClose={() => setWebcam(false)} onShot={(f) => { setWebcam(false); onFiles([f]); }} />}
    </div>
  );
}

function Webcam({ onClose, onShot }: { onClose: () => void; onShot: (f: File) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    let s: MediaStream | null = null;
    navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, width: { ideal: 1920 } }, audio: false })
      .then((st) => { s = st; setStream(st); if (video.current) { video.current.srcObject = st; video.current.play().catch(() => {}); } })
      .catch(() => { toast("Camera not available or permission denied – use Gallery instead.", "err"); closeRef.current(); });
    return () => s?.getTracks().forEach((t) => t.stop());
  }, [facing]);
  const shoot = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    c.toBlob((b) => b && onShot(new File([b], `site_${Date.now()}.jpg`, { type: "image/jpeg" })), "image/jpeg", 0.9);
  };
  return (
    <Modal open onClose={onClose} title="Take a site photo" wide>
      <div className="overflow-hidden rounded-lg bg-black"><video ref={video} playsInline muted className="max-h-[60vh] w-full object-contain" /></div>
      <div className="mt-3 flex flex-wrap justify-between gap-2">
        <button className="btn-ghost" onClick={() => setFacing(facing === "user" ? "environment" : "user")}><RefreshCw size={16} />Switch camera</button>
        <div className="flex gap-2">
          <button className="btn-outline" onClick={onClose}><X size={16} />Cancel</button>
          <button className="btn-primary" disabled={!stream} onClick={shoot}><Camera size={16} />Capture</button>
        </div>
      </div>
    </Modal>
  );
}
