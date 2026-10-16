import type { Express, Request, Response } from "express";
import { FnError } from "../state.js";
import type { FnContext, FnMap } from "../functions/index.js";

const HTTP_BY_CODE: Record<string, number> = {
  "invalid-argument": 400,
  "not-found": 404,
  "failed-precondition": 412,
  internal: 500,
};

/**
 * Local (Express) adapter for the callable functions:
 *   POST /api/call/:name   body: { data }   →   200 { result } | 4xx/5xx { error }
 *
 * The Firebase adapter is the one-liner documented in docs/06-server-and-app.md.
 */
export function mountLocal(app: Express, fns: FnMap, ctx: FnContext): void {
  app.post("/api/call/:name", async (req: Request, res: Response) => {
    const fn = fns[req.params.name];
    if (!fn) {
      res.status(404).json({ error: { code: "not-found", message: `no function '${req.params.name}'` } });
      return;
    }
    try {
      const result = await fn(req.body?.data, ctx);
      res.json({ result });
    } catch (err) {
      if (err instanceof FnError) {
        res.status(HTTP_BY_CODE[err.code] ?? 500).json({ error: { code: err.code, message: err.message } });
      } else {
        console.error(`[fn:${req.params.name}]`, err);
        res.status(500).json({ error: { code: "internal", message: "internal error" } });
      }
    }
  });
}
