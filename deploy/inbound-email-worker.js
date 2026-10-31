// Save by email: a Cloudflare Email Worker that forwards mail sent to save+<token>@<your domain> to Stash.
//
// Setup (once):
//   1. Cloudflare dashboard → your domain → Email → Email Routing → enable it (adds the MX records).
//   2. Workers → Create → paste this file. Settings → Variables:
//        STASH_URL      = https://stash.surajbayas.me
//        INBOUND_SECRET = (same random value as INBOUND_SECRET in the server's .env; mark it "Encrypt")
//   3. Email Routing → Routing rules → Catch-all → Action "Send to a Worker" → this worker.
//   4. Server .env: INBOUND_EMAIL_DOMAIN=<that domain>, INBOUND_SECRET=<same value>, then restart stash-api.
//
// The server only saves mail whose sender is the account's verified email, sent to that account's address.

const MAX_BYTES = 5 * 1024 * 1024;

export default {
  async email(message, env) {
    if (message.rawSize > MAX_BYTES) {
      message.setReject("Message is too large for Stash (5 MB max).");
      return;
    }
    const raw = await new Response(message.raw).arrayBuffer();
    const res = await fetch(`${env.STASH_URL}/api/v1/inbound/email`, {
      method: "POST",
      headers: {
        "Content-Type": "message/rfc822",
        "X-Inbound-Secret": env.INBOUND_SECRET,
        "X-Inbound-To": message.to,
        "X-Inbound-From": message.from,
      },
      body: raw,
    });
    if (res.status === 404) {
      message.setReject("Stash couldn't match this address to your account. Send from the email you use for Stash.");
    } else if (!res.ok) {
      // Throwing makes Cloudflare report a temporary failure, so the sending server retries later.
      throw new Error(`Stash returned ${res.status}`);
    }
  },
};
