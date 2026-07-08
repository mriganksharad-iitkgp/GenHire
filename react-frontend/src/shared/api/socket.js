import io from "socket.io-client";
import { getToken } from "shared/utils/session";

/**
 * Single shared Socket.IO connection for app-wide real-time updates
 * (application created/status-changed/score-updated — see
 * useRealtimeApplications). Separate from the per-page sockets in
 * Chat.jsx/Interview.jsx/MobileRecorder.jsx, which stream proctoring
 * frames and are unrelated to this channel.
 *
 * Module-scoped singleton is safe across tabs because sessionStorage
 * (and therefore each tab's JS module instance) is already tab-scoped.
 */
let socket = null;

export function getAppSocket() {
  if (socket) return socket;

  socket = io(process.env.REACT_APP_API_URL, {
    autoConnect: false,
    auth: (cb) => cb({ token: getToken() }),
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
  });

  return socket;
}

/** Connect (or reconnect with the current tab's token) once a user is authenticated. */
export function connectAppSocket() {
  const s = getAppSocket();
  if (!getToken()) return s;
  if (!s.connected) {
    s.connect();
  }
  return s;
}

/** Disconnect on logout so a stale token isn't reused for the next login in this tab. */
export function disconnectAppSocket() {
  if (socket && socket.connected) {
    socket.disconnect();
  }
}
