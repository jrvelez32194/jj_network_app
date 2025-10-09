import { apiSlice } from "../api/apiSlice";

export const clientsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getClients: builder.query({
      query: () => "clients/",
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({ type: "Clients", id })),
              { type: "Clients", id: "LIST" },
            ]
          : [{ type: "Clients", id: "LIST" }],
    }),

    addClient: builder.mutation({
      query: (client) => ({
        url: "clients/",
        method: "POST",
        body: {
          ...client,
          group_name: client.group_name || "G1",
        },
      }),
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),

    updateClient: builder.mutation({
      query: ({ id, ...patch }) => ({
        url: `clients/${id}`,
        method: "PUT",
        body: patch,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: "Clients", id },
        { type: "Clients", id: "LIST" },
      ],
    }),

    deleteClient: builder.mutation({
      query: (id) => ({
        url: `clients/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),

    // ✅ Bulk delete
    deleteClients: builder.mutation({
      query: (ids) => {
        const searchParams = new URLSearchParams();
        ids.forEach((id) => searchParams.append("client_ids", id));
        return {
          url: "clients/",
          method: "DELETE",
          params: searchParams,
        };
      },
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),

    // ✅ Sync clients from FB API
    syncClients: builder.mutation({
      query: () => ({
        url: "clients/sync",
        method: "POST",
      }),
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),

    // ✅ Paid / Unpaid handlers
    setPaidBulk: builder.mutation({
      query: (clientIds) => ({
        url: "/clients/set_paid_bulk",
        method: "POST",
        body: clientIds,
      }),
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),
    setPaid: builder.mutation({
      query: (clientId) => ({
        url: `clients/${clientId}/set_paid`,
        method: "POST",
      }),
      invalidatesTags: (result, error, clientId) => [
        { type: "Clients", id: clientId },
        { type: "Clients", id: "LIST" },
      ],
    }),
    setUnpaidBulk: builder.mutation({
      query: (clientIds) => ({
        url: "clients/set_unpaid_bulk",
        method: "POST",
        body: clientIds,
      }),
      invalidatesTags: [{ type: "Clients", id: "LIST" }],
    }),
    setUnpaid: builder.mutation({
      query: (clientId) => ({
        url: `clients/${clientId}/set_unpaid`,
        method: "POST",
      }),
      invalidatesTags: (result, error, clientId) => [
        { type: "Clients", id: clientId },
        { type: "Clients", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetClientsQuery,
  useAddClientMutation,
  useUpdateClientMutation,
  useDeleteClientMutation,
  useDeleteClientsMutation,
  useSyncClientsMutation,
  useSetPaidBulkMutation,
  useSetPaidMutation,
  useSetUnpaidBulkMutation,
  useSetUnpaidMutation,
} = clientsApi;
