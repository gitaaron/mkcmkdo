import { WebSocketServer, WebSocket, type RawData } from "ws";
import type { Server, IncomingMessage } from "node:http";
import type { Duplex } from "node:stream";
import type { Store, Telemetry } from "./state.js";
import type { FrameBus } from "./stream.js";
import type { Recordings, RecordingMeta } from "./recordings.js";

type DeviceKind = "head" | "sim";

interface DeviceConn {
  ws: WebSocket;
  kind: DeviceKind;
  expectingFrame: boolean;
}

/**
 * WebSocket hub.
 *   /ws         app clients   — receive { type:"state", ... } broadcasts
 *   /ws/device  head/sim — protocol in docs/05-device-software.md
 *
 * In a Firebase migration the app side of this becomes a Firestore
 * `onSnapshot` listener; the device side stays a plain socket server.
 */
export class Hub {
  private apps = new WebSocketServer({ noServer: true });
  private devices = new WebSocketServer({ noServer: true });
  private deviceConns = new Set<DeviceConn>();

  constructor(private store: Store, private frames: FrameBus, private recordings: Recordings) {
    store.on("change", () => {
      this.broadcastState();
      this.sendToDevices({ type: "state", state: store.get().state });
    });
    recordings.on("change", (list: RecordingMeta[]) => {
      this.broadcastToApps({ type: "recordings", recordings: list });
    });

    this.apps.on("connection", (ws) => {
      ws.send(this.statePayload());
      ws.send(JSON.stringify({ type: "recordings", recordings: recordings.list() }));
    });

    this.devices.on("connection", (ws) => {
      const conn: DeviceConn = { ws, kind: "sim", expectingFrame: false };
      this.deviceConns.add(conn);
      ws.on("message", (data, isBinary) => this.onDeviceMessage(conn, data, isBinary));
      ws.on("close", () => {
        this.deviceConns.delete(conn);
        this.updatePresence();
      });
      // No state push on connect: the head owns its state (the tag, or a
      // lock-on, can start a session with no server in reach) and reports it
      // right after its hello. Pushing ours first would stop a recording every time the
      // server restarted or the Wi-Fi blinked.
    });
  }

  attach(server: Server): void {
    server.on("upgrade", (req: IncomingMessage, socket: Duplex, head: Buffer) => {
      const path = new URL(req.url ?? "/", "http://x").pathname;
      const target = path === "/ws" ? this.apps : path === "/ws/device" ? this.devices : null;
      if (!target) {
        socket.destroy();
        return;
      }
      target.handleUpgrade(req, socket, head, (ws) => target.emit("connection", ws, req));
    });
  }

  hasRealHead(): boolean {
    return [...this.deviceConns].some((c) => c.kind === "head");
  }

  private onDeviceMessage(conn: DeviceConn, data: RawData, isBinary: boolean): void {
    if (isBinary) {
      if (conn.expectingFrame) {
        conn.expectingFrame = false;
        this.frames.push(data as Buffer);
      }
      return;
    }
    let msg: any;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }
    switch (msg.type) {
      case "hello":
        conn.kind = msg.device;
        if (msg.mode && msg.mode !== this.store.get().mode) {
          // A without_uwb head on a with_uwb server still works, but the apps
          // would word everything for the wrong build. Say so loudly.
          console.warn(
            `[hub] head reports mode '${msg.mode}' but TRACKING_MODE is ` +
              `'${this.store.get().mode}' — restart the server with TRACKING_MODE=${msg.mode}`,
          );
        }
        this.updatePresence();
        break;
      case "frame":
        conn.expectingFrame = true;
        break;
      case "telemetry":
        this.store.patch({ telemetry: msg as Telemetry });
        break;
      case "stateReport":
        // The head changed state on its own — with_uwb: the tag switched on
        // or off; either build: a lock-on started recording, the search gave
        // up on an empty room, the battery ran low. Adopt it, so the
        // apps follow and the next server → device message does not undo it.
        if (["off", "idle", "tracking", "recording"].includes(msg.state) &&
            msg.state !== this.store.get().state) {
          this.store.patch({ state: msg.state });
        }
        break;
      case "tagButton":
        // with_uwb only: long press on the wearable toggles recording
        if (this.store.get().mode !== "with_uwb") break;
        if (msg.kind === "long") {
          const s = this.store.get().state;
          if (s === "tracking") this.store.patch({ state: "recording" });
          else if (s === "recording") this.store.patch({ state: "tracking" });
        }
        break;
      case "lost":
        // with_uwb only: head lost the tag past the timeout → back to idle
        // (saves recording). Without UWB a lost person means sweep again, which
        // the head handles itself; it never drops to idle on its own.
        if (this.store.get().mode !== "with_uwb") break;
        if (this.store.get().state !== "off") this.store.patch({ state: "idle" });
        break;
      case "uploadProgress":
        // head → apps: {name, sent, total} while a recording uploads
        this.broadcastToApps(msg);
        break;
    }
  }

  private updatePresence(): void {
    const online = [...this.deviceConns].some((c) => c.kind === "head" || c.kind === "sim");
    if (online !== this.store.get().deviceOnline) {
      this.store.patch({ deviceOnline: online });
    }
  }

  private statePayload(): string {
    return JSON.stringify({ type: "state", ...this.store.get() });
  }

  private broadcastState(): void {
    this.broadcastToApps(null);
  }

  private broadcastToApps(msg: unknown | null): void {
    const payload = msg === null ? this.statePayload() : JSON.stringify(msg);
    for (const ws of this.apps.clients) {
      if (ws.readyState === WebSocket.OPEN) ws.send(payload);
    }
  }

  private sendToDevices(msg: unknown, kind?: DeviceKind): void {
    const payload = JSON.stringify(msg);
    for (const c of this.deviceConns) {
      if (kind && c.kind !== kind) continue;
      if (c.ws.readyState === WebSocket.OPEN) c.ws.send(payload);
    }
  }
}
