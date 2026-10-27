/**
 * Make the first admin — nobody can sign up, so someone has to exist before
 * the app's admin page can add anyone else.
 *
 *   npm run add-admin -- <email> <password>            the deployed project
 *                                                      (gcloud application-default credentials)
 *   FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 GCLOUD_PROJECT=demo-sportcam \
 *     npm run add-admin -- <email> <password>          the emulator
 *
 * Creates the account if it doesn't exist (an existing one keeps its
 * password) and gives it the `admin` claim.
 */
import { initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { MIN_PASSWORD } from "./auth.js";

const [email, password] = process.argv.slice(2);
if (!email || !password || password.length < MIN_PASSWORD) {
  console.error(`usage: npm run add-admin -- <email> <password, at least ${MIN_PASSWORD} characters>`);
  process.exit(1);
}

initializeApp(process.env.GCLOUD_PROJECT ? { projectId: process.env.GCLOUD_PROJECT } : undefined);
const auth = getAuth();
const user = await auth.getUserByEmail(email).catch(() => auth.createUser({ email, password }));
await auth.setCustomUserClaims(user.uid, { ...user.customClaims, admin: true });
console.log(`${email} is an admin (${user.uid})`);
