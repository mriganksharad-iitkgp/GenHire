import { useEffect, useRef } from "react";
import { connectAppSocket } from "../services/socket";

/**
 * Subscribes to the shared `application_update` socket channel (emitted by
 * application_controller.py on apply / status change / interview score
 * update — see python-backend/extensions.py) and invokes `onUpdate` for
 * each event, so callers can patch their local application list in place
 * instead of waiting for a manual refresh.
 *
 * `onUpdate` receives `(type, application)` where type is one of
 * "created" | "status_changed" | "score_updated".
 *
 * Does not disconnect the socket on unmount — it's a shared app-wide
 * connection that may still be needed by another mounted consumer.
 */
export default function useRealtimeApplications(onUpdate) {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    const socket = connectAppSocket();

    const handleUpdate = (payload) => {
      if (!payload || !payload.application) return;
      onUpdateRef.current?.(payload.type, payload.application);
    };

    socket.on("application_update", handleUpdate);
    return () => {
      socket.off("application_update", handleUpdate);
    };
  }, []);
}
