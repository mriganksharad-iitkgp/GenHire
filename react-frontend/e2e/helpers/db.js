// Direct access to the throw-away test database. It stands in for the inbox:
// email is disabled, so verification / reset / invite tokens that would arrive
// by mail are read (or, for invites, replaced by a known one) here. It is not
// used to fake product behaviour.
import { createHash } from 'node:crypto';
import { MongoClient } from 'mongodb';

let client;
export async function db() {
  client ||= await MongoClient.connect(process.env.E2E_MONGO_URI);
  return client.db(process.env.E2E_DB_NAME);
}
export const userByEmail = async (email) => (await db()).collection('users').findOne({ email_lower: email.toLowerCase() });

// Email is disabled, so the raw invite magic-link token is never visible. This
// stands in for "the candidate received the email": it swaps the stored hash
// of a real invite token for the hash of a token we know. Same hashing the
// backend uses (sha256(raw + INVITE_TOKEN_SECRET)).
export async function knownInviteToken(inviteEmail) {
  const d = await db();
  // invites are created by a background worker, so wait for the account to appear
  let user = null;
  for (let i = 0; i < 60 && !user; i++) {
    user = await d.collection('users').findOne({ email: inviteEmail.toLowerCase() });
    if (!user) await new Promise(r => setTimeout(r, 250));
  }
  if (!user) throw new Error(`no invited user for ${inviteEmail}`);
  for (let i = 0; i < 60; i++) {
    if (await d.collection('invite_tokens').findOne({ user_id: user._id, consumed_at: null })) break;
    await new Promise(r => setTimeout(r, 250));
  }
  const raw = `e2e-invite-${Math.random().toString(36).slice(2)}`;
  const token_hash = createHash('sha256').update(raw + process.env.E2E_INVITE_SECRET).digest('hex');
  const res = await d.collection('invite_tokens').updateOne({ user_id: user._id, consumed_at: null }, { $set: { token_hash } });
  if (!res.matchedCount) throw new Error('no unconsumed invite token found');
  return { raw, user };
}
