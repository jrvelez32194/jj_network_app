// src/features/messages/messagesApi.js
import { apiSlice } from "../api/apiSlice";

export const messagesApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ POST /messages/send with JSON body
    sendToClients: builder.mutation({
      query: ({ title, message, client_ids }) => ({
        url: "messages/send",
        method: "POST",
        body: {
          title, // now sending actual title
          message, // now sending actual message
          client_ids, // still array of ints
        },
      }),
    }),
  }),
});

export const { useSendToClientsMutation } = messagesApi;
