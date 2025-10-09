// src/features/messages/messagesApi.js
import { apiSlice } from "../api/apiSlice";

export const messagesApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ POST /messages/send with JSON body
    sendToClients: builder.mutation({
      query: ({ template_id, client_ids }) => ({
        url: "messages/send",
        method: "POST",
        body: {
          template_id,
          client_ids, // ✅ backend expects array of ints
        },
      }),
    }),
  }),
});

export const { useSendToClientsMutation } = messagesApi;
