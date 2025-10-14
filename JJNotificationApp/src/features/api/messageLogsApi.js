import { apiSlice } from "../api/apiSlice";

export const messageLogsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ Get all message logs
    getMessageLogs: builder.query({
      query: () => "message_logs/",
      providesTags: ["MessageLogs"],
    }),

    // Optional: get a single log by ID
    getMessageLog: builder.query({
      query: (id) => `message_logs/${id}/`,
      providesTags: (result, error, id) => [{ type: "MessageLogs", id }],
    }),

    // Optional: delete a log
    deleteMessageLog: builder.mutation({
      query: (id) => ({
        url: `message_logs/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["MessageLogs"],
    }),

    // Optional: bulk delete logs
    deleteMessageLogs: builder.mutation({
      query: (ids) => {
        const searchParams = new URLSearchParams();
        ids.forEach((id) => searchParams.append("log_ids", id));
        return {
          url: "message_logs/",
          method: "DELETE",
          params: searchParams,
        };
      },
      invalidatesTags: ["MessageLogs"],
    }),

    // ✅ Delete ALL logs
    deleteAllMessageLogs: builder.mutation({
      query: () => ({
        url: `message_logs/all`,
        method: "DELETE",
      }),
      invalidatesTags: ["MessageLogs"],
    }),
  }),
});

export const {
  useGetMessageLogsQuery,
  useGetMessageLogQuery,
  useDeleteMessageLogMutation,
  useDeleteMessageLogsMutation,
  useDeleteAllMessageLogsMutation,
} = messageLogsApi;
