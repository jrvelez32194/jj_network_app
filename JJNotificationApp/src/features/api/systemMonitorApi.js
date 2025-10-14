import { apiSlice } from "./apiSlice";

export const systemMonitorApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ Get system resource usage (CPU, Memory, Disk)
    getSystemStatus: builder.query({
      query: () => "system-status",
      providesTags: (result) =>
        result ? [{ type: "SystemMonitor", id: "STATUS" }] : [],
      // ✅ Live auto-refresh every 5 seconds
      pollingInterval: 5000,
    }),
  }),
});

export const { useGetSystemStatusQuery } = systemMonitorApi;
