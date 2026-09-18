import { WebSocketServer, WebSocket, type RawData } from "ws";
import type { Server, IncomingMessage } from "node:http";
import type { Duplex } from "node:stream";
import type { Store, Telemetry } from "./state.js";
import type { FrameBus } from "./stream.js";

type DeviceKind = "head" | "base" | "sim";

interface DeviceConn {
  ws: WebSocket;
  kind: DeviceKind;
  expectingFrame: boolean;
}

/**
 * WebSocket hub.
 *   /ws         app clients   — receive { type:"state", ... } broadcasts
 *   /ws/device  head/base/sim — protocol in docs/05-device-software.md
 *
 * In a Firebase migration the app side of this becomes a Firestore
 * `onSnapshot` listener; the device side stays a plain socket server.
 */
export class Hub {
  private apps = new WebSocketServer({ noServer: true });
  private devices = new WebSocketServer({ noServer: true });
  private deviceConns = new Set<DeviceConn>();

  constructor(private store: Store, private frames: FrameBus) {
    store.on("change", () => {
      this.broadcastState();
      this.sendToDevices({ type: "state", state: store.get().state });
    });

    this.apps.on("connection", (ws) => {
      ws.send(this.statePayload());
    });

    this.devices.on("connection", (ws) => {
      const conn: DeviceConn = { ws, kind: "sim", expectingFrame: false };
      this.deviceConns.add(conn);
      ws.on("message", (data, isBinary) => this.onDeviceMessage(conn, data, isBinary));
      ws.on("close", () => {
        this.deviceConns.delete(conn);
        this.updatePresence();
      });
      ws.send(JSON.stringify({ type: "state", state: this.store.get().state }));
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
        this.updatePresence();
        break;
      case "frame":
        conn.expectingFrame = true;
        break;
      case "telemetry":
        this.store.patch({ telemetry: msg as Telemetry });
        break;
      case "panVel":
        // relay head → base
        this.sendToDevices(msg, "base");
        break;
      case "tagButton":
        // long press on the wearable toggles recording
        if (msg.kind === "long") {
          const s = this.store.get().state;
          if (s === "tracking") this.store.patch({ state: "recording" });
          else if (s === "recording") this.store.patch({ state: "tracking" });
        }
        break;
      case "lost":
        // head lost the tag past the timeout → back to idle (saves recording)
        if (this.store.get().state !== "off") this.store.patch({ state: "idle" });
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
    const payload = this.statePayload();
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
