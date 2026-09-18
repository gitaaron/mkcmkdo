import { EventEmitter } from "node:events";
import type { Request, Response } from "express";

const BOUNDARY = "sportcamframe";

/**
 * Latest-frame buffer + MJPEG relay.
 * Devices (or the simulator) push JPEG buffers in; any number of app clients
 * hold a multipart/x-mixed-replace response open and receive each frame.
 */
export class FrameBus extends EventEmitter {
  private latest: Buffer | null = null;

  push(jpeg: Buffer): void {
    this.latest = jpeg;
    this.emit("frame", jpeg);
  }

  handler = (_req: Request, res: Response): void => {
    res.writeHead(200, {
      "Content-Type": `multipart/x-mixed-replace; boundary=${BOUNDARY}`,
      "Cache-Control": "no-store",
      Connection: "close",
    });
    const write = (jpeg: Buffer) => {
      res.write(`--${BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ${jpeg.length}\r\n\r\n`);
      res.write(jpeg);
      res.write("\r\n");
    };
    if (this.latest) write(this.latest);
    this.on("frame", write);
    res.on("close", () => this.off("frame", write));
  };
}
