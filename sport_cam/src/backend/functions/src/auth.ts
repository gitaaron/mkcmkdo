/**
 * Who is calling: people sign in to the phone app with an email and a
 * password (Firebase Authentication), and every call the app makes here
 * carries their ID token as `Authorization: Bearer <token>`.
 *
 * There is no public sign-up. An admin (custom claim `admin: true`) adds
 * people from the app's admin page (`createUser`); the first admin is made
 * with `npm run add-admin` (src/backend/functions/src/add-admin.ts).
 *
 * The camera itself never signs in: it names itself with its camera key.
 */
import type { Request } from "express";
import { getAuth } from "firebase-admin/auth";
import { FnError } from "./errors.js";

export interface User {
  uid: string;
  email: string | null;
  admin: boolean;
}

export async function userOf(req: Request): Promise<User> {
  const m = /^Bearer (.+)$/.exec(req.header("authorization") ?? "");
  if (!m) throw new FnError("unauthenticated", "sign in first");
  try {
    const t = await getAuth().verifyIdToken(m[1]!);
    return { uid: t.uid, email: t.email ?? null, admin: t.admin === true };
  } catch {
    throw new FnError("unauthenticated", "your sign-in has expired — sign in again");
  }
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const MIN_PASSWORD = 8;

function requireAdmin(user: User): void {
  if (!user.admin) throw new FnError("permission-denied", "only an admin can do that");
}

/** Admin only: add a person. They sign in with this email and password. */
export async function createUser(user: User, data: any): Promise<{ uid: string; email: string; admin: boolean }> {
  requireAdmin(user);
  const email = typeof data?.email === "string" ? data.email.trim().toLowerCase() : "";
  const password = data?.password;
  const admin = data?.admin === true;
  if (!EMAIL_RE.test(email)) throw new FnError("invalid-argument", "that isn't an email address");
  if (typeof password !== "string" || password.length < MIN_PASSWORD) {
    throw new FnError("invalid-argument", `the password needs at least ${MIN_PASSWORD} characters`);
  }
  try {
    const created = await getAuth().createUser({ email, password });
    if (admin) await getAuth().setCustomUserClaims(created.uid, { admin: true });
    return { uid: created.uid, email, admin };
  } catch (err: any) {
    if (err?.code === "auth/email-already-exists") {
      throw new FnError("already-exists", "someone already has that email");
    }
    throw err;
  }
}

/** Admin only: everyone who can sign in. */
export async function listUsers(user: User): Promise<{ users: { uid: string; email: string | null; admin: boolean }[] }> {
  requireAdmin(user);
  const { users } = await getAuth().listUsers(1000);
  return {
    users: users
      .map((u) => ({ uid: u.uid, email: u.email ?? null, admin: u.customClaims?.admin === true }))
      .sort((a, b) => (a.email ?? "").localeCompare(b.email ?? "")),
  };
}
