import { clerkSetup } from "@clerk/testing/playwright";

// Emails containing "+clerk_test" are Clerk test addresses: no mail is ever sent to them.
export const E2E_USERS = [
  process.env.E2E_USER_1 ?? "zetamaxx-e2e-1+clerk_test@example.com",
  process.env.E2E_USER_2 ?? "zetamaxx-e2e-2+clerk_test@example.com",
];

const CLERK_API = "https://api.clerk.com/v1";

async function clerkApi(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${CLERK_API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${process.env.CLERK_SECRET_KEY}`, "Content-Type": "application/json" },
  });
}

/** Creates the test user in the Clerk development instance unless it is already there. */
async function ensureUser(email: string, username: string): Promise<void> {
  const found = await clerkApi(`/users?email_address=${encodeURIComponent(email)}`);
  if (!found.ok) throw new Error(`Clerk user lookup failed (${found.status}): ${await found.text()}`);
  if (((await found.json()) as unknown[]).length > 0) return;

  const base = { email_address: [email], skip_password_requirement: true };
  // Instances without usernames switched on reject the field, so fall back to no username.
  for (const body of [{ ...base, username }, base]) {
    const created = await clerkApi("/users", { method: "POST", body: JSON.stringify(body) });
    if (created.ok) return;
    if (created.status !== 422) throw new Error(`Could not create ${email} (${created.status}): ${await created.text()}`);
  }
  throw new Error(`Could not create ${email}: Clerk rejected it. Create the user in the Clerk dashboard instead.`);
}

export default async function globalSetup(): Promise<void> {
  const secret = process.env.CLERK_SECRET_KEY ?? "";
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || !secret) {
    throw new Error("The end-to-end test needs NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY in .env");
  }
  if (!secret.startsWith("sk_test_")) {
    throw new Error("The end-to-end test only runs against a Clerk development instance (sk_test_ key)");
  }
  await ensureUser(E2E_USERS[0], "zeta_e2e_one");
  await ensureUser(E2E_USERS[1], "zeta_e2e_two");
  // Fetches a testing token so Clerk's bot protection lets the automated browser sign in.
  await clerkSetup({ publishableKey: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY });
}
