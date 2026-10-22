import { ref, type Ref } from "vue";

/**
 * A Boxes on / off switch, remembered in this browser. The recording player
 * and the live view each have their own (`storageKey`).
 */
export function useShowBoxes(storageKey: string): { show: Ref<boolean>; toggle: () => void } {
  const show = ref(read());

  function read(): boolean {
    try {
      return localStorage.getItem(storageKey) !== "0";
    } catch {
      return true;
    }
  }

  function toggle(): void {
    show.value = !show.value;
    try {
      localStorage.setItem(storageKey, show.value ? "1" : "0");
    } catch {
      /* storage blocked: lasts for this visit */
    }
  }

  return { show, toggle };
}
