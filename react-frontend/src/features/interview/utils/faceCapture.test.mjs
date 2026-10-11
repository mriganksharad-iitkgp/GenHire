import test from "node:test";
import assert from "node:assert/strict";
import { captureProgress, facePosition, FACE_HOLD_MS } from "./faceCapture.js";

const face = (originX = 210, originY = 100, width = 200, height = 220) => ({ boundingBox: { originX, originY, width, height } });
test("capture requires exactly one centered face at a useful distance", () => {
  assert.equal(facePosition([], 640, 480).ready, false);
  assert.equal(facePosition([face(), face()], 640, 480).ready, false);
  assert.equal(facePosition([face(0)], 640, 480).ready, false);
  assert.equal(facePosition([face(210, 100, 70, 90)], 640, 480).ready, false);
  assert.equal(facePosition([face(90, 0, 500, 470)], 640, 480).ready, false);
  assert.equal(facePosition([face()], 640, 480).ready, true);
});
test("hold resets for lost faces or movement and captures only after a stable interval", () => {
  const position = facePosition([face()], 640, 480);
  let state = captureProgress(null, position, 0);
  assert.equal(captureProgress(state, position, FACE_HOLD_MS - 1).captured, false);
  assert.equal(captureProgress(state, position, FACE_HOLD_MS).captured, true);
  state = captureProgress(state, { ...position, x: position.x + 0.1 }, 900);
  assert.equal(state.progress, 0);
  state = captureProgress(state, { ready: false }, 1100);
  assert.equal(state.since, null);
  state = captureProgress(state, position, 1200);
  assert.equal(state.captured, false);
});
