/**
 * Who owns a recording, and who may stop it.
 *
 * Several people share one camera. Whoever taps Record gets a **session
 * secret**: a random string only their phone holds. The camera (or this API,
 * when the tap came through Firebase) keeps just its SHA-256, the
 * `sessionHash`, and:
 *
 *   - refuses to stop the session (stop, sleep, stop tracking) unless the
 *     call carries the secret, so only the person recording can stop it;
 *   - stamps every clip of the session with the hash, its `claimHash`.
 *
 * Ownership then reaches the library through `claims/{hash}`: the app
 * registers each secret it holds against the signed-in person
 * (`claimRecordings`), and a clip whose claimHash is registered belongs to
 * them — whether the clip uploaded before the claim or after. Nobody else
 * can claim it without the secret, and the hash alone is no use.
 *
 * With UWB, a tag paired to a phone works the same way: the pairing secret
 * is that phone's session secret for every session the tag starts.
 */
import { createHash, randomBytes } from "node:crypto";
import { FieldValue, Timestamp, getFirestore, type Transaction } from "firebase-admin/firestore";
import type { User } from "./auth.js";
import { FnError } from "./errors.js";

export const HASH_RE = /^[0-9a-f]{64}$/;
const SECRET_RE = /^[A-Za-z0-9_-]{16,128}$/;
const MAX_SECRETS = 100;

export const hashSecret = (secret: string) => createHash("sha256").update(secret).digest("hex");
export const newSecret = () => randomBytes(32).toString("base64url");
export const isSecret = (s: unknown): s is string => typeof s === "string" && SECRET_RE.test(s);

/** The well-formed secrets in `data.secrets` (the app sends every one it holds). */
export function secretsOf(data: any): string[] {
  const list = Array.isArray(data?.secrets) ? data.secrets : [];
  return list.filter(isSecret).slice(0, MAX_SECRETS);
}

export const holds = (secrets: string[], hash: string) => secrets.some((s) => hashSecret(s) === hash);

const claimRef = (hash: string) => getFirestore().collection("claims").doc(hash);

/** The person a session hash belongs to, if anyone has claimed it. */
export async function ownerOf(hash: string | null): Promise<string | null> {
  if (!hash) return null;
  const snap = await claimRef(hash).get();
  return snap.exists ? (snap.get("owner") as string) : null;
}

/**
 * Inside a transaction: register `hash` to `uid`, unless it is already
 * someone else's. Reads, so call it before the transaction's writes.
 */
export async function registerIn(tx: Transaction, hash: string, uid: string): Promise<boolean> {
  const ref = claimRef(hash);
  const snap = await tx.get(ref);
  if (snap.exists) return snap.get("owner") === uid;
  tx.set(ref, { owner: uid, createdAt: Timestamp.now() });
  return true;
}

/**
 * `claimRecordings({secrets})`: register each secret to the caller and hand
 * them every clip already uploaded under it. Safe to repeat. A secret that
 * is somebody else's is refused, and counted.
 */
export async function claimRecordings(user: User, data: any): Promise<{ claimed: number; refused: number }> {
  const db = getFirestore();
  let claimed = 0;
  let refused = 0;
  for (const secret of new Set(secretsOf(data))) {
    const hash = hashSecret(secret);
    const mine = await db.runTransaction((tx) => registerIn(tx, hash, user.uid));
    if (!mine) {
      refused++;
      continue;
    }
    const clips = await db.collection("recordings").where("claimHash", "==", hash).get();
    for (const clip of clips.docs) {
      if (clip.get("owner") == null) {
        await clip.ref.update({ owner: user.uid, claimedAt: FieldValue.serverTimestamp() });
        claimed++;
      }
    }
  }
  return { claimed, refused };
}

export function permissionDenied(): FnError {
  return new FnError("permission-denied", "only the phone that started this recording can stop it");
}
