import { ref } from "vue";

/**
 * The camera key: a long random string shared by the camera and its apps.
 * It names the camera's Firestore document and goes with every API call, so
 * holding it is what lets you watch and control the camera.
 *
 * It arrives once in the link the setup prints (…/#key=<key>), is kept in
 * this browser, and is wiped from the address bar so it isn't shared by
 * accident. In dev the simulated camera's key is the default.
 */
const STORAGE = "sportcam.cameraKey";
const DEV_KEY = import.meta.env.VITE_CAMERA_KEY ?? "dev-camera-key";

function initial(): string | null {
  const m = /[#&]key=([A-Za-z0-9_-]{8,64})/.exec(location.hash);
  if (m) {
    save(m[1]!);
    history.replaceState(null, "", location.pathname + location.search);
    return m[1]!;
  }
  try {
    const kept = localStorage.getItem(STORAGE);
    if (kept) return kept;
  } catch {
    /* storage blocked */
  }
  return import.meta.env.DEV ? DEV_KEY : null;
}

function save(key: string): void {
  try {
    localStorage.setItem(STORAGE, key);
  } catch {
    /* storage blocked: lasts for this visit */
  }
}

export const cameraKey = ref<string | null>(initial());

export function setCameraKey(key: string): boolean {
  const k = key.trim();
  if (!/^[A-Za-z0-9_-]{8,64}$/.test(k)) return false;
  save(k);
  cameraKey.value = k;
  return true;
}
