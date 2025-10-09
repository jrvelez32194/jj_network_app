import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

const API_BASE_URL =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000" // Dev direct to FastAPI
    : "/api/"; // Docker/Nginx proxy

export const apiSlice = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: API_BASE_URL,
  }),
  tagTypes: ["Clients", "Templates", "Messages", "MessageLogs"],
  refetchOnFocus: false,
  refetchOnReconnect: false,
  keepUnusedDataFor: 60, // keep cache for 1 minute
  endpoints: () => ({}),
});
