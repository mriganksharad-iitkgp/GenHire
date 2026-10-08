import test from "node:test";
import assert from "node:assert/strict";
import { retryAfterSeconds } from "./retry.js";
const response = (header) => ({ headers: new Headers(header ? { "Retry-After": header } : {}) });
test("retry delay supports numeric headers, payload fallback and HTTP dates", () => {
  assert.equal(retryAfterSeconds(response("17"), { retry_after: 3 }), 17);
  assert.equal(retryAfterSeconds(response(null), { retry_after: 8 }), 8);
  assert.equal(retryAfterSeconds(response("Thu, 01 Jan 1970 00:00:09 GMT"), {}, 2000), 7);
});
test("invalid, negative and excessive retry hints stay bounded", () => {
  assert.equal(retryAfterSeconds(response("-4")), 0);
  assert.equal(retryAfterSeconds(response("invalid")), 0);
  assert.equal(retryAfterSeconds(response("999999")), 86400);
  assert.equal(retryAfterSeconds(response(null), { retry_after: 2.2 }), 3);
});

