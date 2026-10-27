export type FnErrorCode =
  | "failed-precondition"
  | "invalid-argument"
  | "not-found"
  | "unauthenticated"
  | "permission-denied"
  | "already-exists"
  | "internal";

export class FnError extends Error {
  constructor(public code: FnErrorCode, message: string) {
    super(message);
  }
}

export const HTTP_BY_CODE: Record<FnErrorCode, number> = {
  "invalid-argument": 400,
  unauthenticated: 401,
  "permission-denied": 403,
  "not-found": 404,
  "already-exists": 409,
  "failed-precondition": 412,
  internal: 500,
};
