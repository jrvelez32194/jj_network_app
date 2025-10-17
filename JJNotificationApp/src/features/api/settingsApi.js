import { apiSlice } from "./apiSlice";

export const settingsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    // ✅ Get Messenger Setting
    getMessengerSetting: builder.query({
      query: () => "settings/messenger",
      providesTags: ["MessengerSetting"],
    }),

    // ✅ Update Messenger Setting
    updateMessengerSetting: builder.mutation({
      query: (data) => ({
        url: "settings/messenger",
        method: "POST",
        body: data,
      }),
      invalidatesTags: ["MessengerSetting"],
    }),
  }),
});

export const {
  useGetMessengerSettingQuery,
  useUpdateMessengerSettingMutation,
} = settingsApi;
