import { useEffect, useRef } from "react";
import { clientsApi } from "../features/api/clientsApi";

export function useWebSocketManager({ showToast, dispatch }) {
  const reconnectDelayRef = useRef(1000);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);

  const connect = () => {
    // 🔒 Close old socket before reconnecting
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.info("✅ WebSocket connected");
      reconnectDelayRef.current = 1000;

      // 🔄 Heartbeat every 30s
      if (heartbeatIntervalRef.current)
        clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN)
          ws.send(JSON.stringify({ type: "ping" }));
      }, 30000);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.event) {
        case "state_update":
          dispatch(
            clientsApi.util.updateQueryData(
              "getClients",
              undefined,
              (draft) => {
                const client = draft.find((c) => c.id === Number(data.id));
                if (client && client.state !== data.state) {
                  client.state = data.state;
                  showToast(
                    `${data.client} is now ${data.state}`,
                    data.state === "DOWN" ? "error" : "success"
                  );
                }
              }
            )
          );
          break;

        case "billing_update":
          dispatch(
            clientsApi.util.updateQueryData(
              "getClients",
              undefined,
              (draft) => {
                const client = draft.find(
                  (c) => c.id === Number(data.client_id)
                );
                if (!client) return;

                if (data.billing_date) client.billing_date = data.billing_date;
                if (data.status && client.status !== data.status) {
                  client.status = data.status;
                  showToast(`${client.name} is now ${data.status}`, "info");
                }
              }
            )
          );
          break;

        case "billing_update_bulk":
          showToast("Bulk billing update completed.", "success");
          dispatch(
            clientsApi.util.invalidateTags([{ type: "Clients", id: "LIST" }])
          );
          break;

        default:
          if (process.env.NODE_ENV === "development") {
            console.log("📩 Unknown event:", data);
          }
      }
    };

    ws.onclose = () => {
      console.warn("⚠️ WebSocket closed. Attempting reconnect...");
      clearInterval(heartbeatIntervalRef.current);
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.error("❌ WebSocket error:", err);
      ws.close();
    };
  };

  const scheduleReconnect = () => {
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 2,
        30000
      );
    }, reconnectDelayRef.current);
  };

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      clearInterval(heartbeatIntervalRef.current);
      clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  return wsRef;
}
