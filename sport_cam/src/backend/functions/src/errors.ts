export type FnErrorCode = "failed-precondition" | "invalid-argument" | "not-found" | "internal";

export class FnError extends Error {
  constructor(public code: FnErrorCode, message: string) {
    super(message);
  }
}

export const HTTP_BY_CODE: Record<FnErrorCode, number> = {
  "invalid-argument": 400,
  "not-found": 404,
  "failed-precondition": 412,
  internal: 500,
};
