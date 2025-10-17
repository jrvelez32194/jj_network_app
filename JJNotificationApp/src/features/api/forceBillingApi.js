import { apiSlice } from "./apiSlice";

export const forceBillingApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ Fetch billable clients list
    getBillableClients: builder.query({
      query: () => "/force/clients", // <-- adjust only if you have a /force/clients route
      providesTags: ["BillingClients"],
    }),

    // ✅ Force billing for one specific client
    notifyClient: builder.mutation({
      query: (clientId) => ({
        url: `/force/client/${clientId}`,
        method: "POST",
        // optional params:
        // params: { mode: "notification" } // or "enforce"
      }),
      invalidatesTags: ["BillingClients"],
    }),

    // ✅ Force billing for all (or group)
    notifyAllClients: builder.mutation({
      query: ({ mode = "notification", group = null } = {}) => ({
        url: `/force/run`,
        method: "POST",
        params: { mode, ...(group ? { group } : {}) },
      }),
      invalidatesTags: ["BillingClients"],
    }),
  }),
});

export const {
  useGetBillableClientsQuery,
  useNotifyClientMutation,
  useNotifyAllClientsMutation,
} = forceBillingApi;
