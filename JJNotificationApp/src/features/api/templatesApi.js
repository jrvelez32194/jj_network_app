import { apiSlice } from "./apiSlice";
export const templatesApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getTemplates: builder.query({
      query: () => "templates/",
      providesTags: ["Templates"],
    }),

    getTemplatesDropdown: builder.query({
      query: () => "templates/",
      transformResponse: (response) => {
        // If API returns { results: [...] }, unwrap it
        return response.results || response;
      },
      providesTags: ["Templates"],
    }),

    addTemplate: builder.mutation({
      query: (template) => ({
        url: "templates/",
        method: "POST",
        body: template,
      }),
      invalidatesTags: ["Templates"],
    }),

    updateTemplate: builder.mutation({
      query: ({ id, ...rest }) => ({
        url: `templates/${id}`,
        method: "PUT",
        body: rest,
      }),
      invalidatesTags: ["Templates"],
    }),

    deleteTemplate: builder.mutation({
      query: (id) => ({
        url: `templates/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Templates"],
    }),

    // ✅ Fixed bulk delete
    deleteTemplates: builder.mutation({
      query: (ids) => ({
        url: `templates/?${ids.map((id) => `template_ids=${id}`).join("&")}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Templates"],
    }),
  }),
});

export const {
  useGetTemplatesQuery,
  useGetTemplatesDropdownQuery,
  useAddTemplateMutation,
  useUpdateTemplateMutation,
  useDeleteTemplateMutation,
  useDeleteTemplatesMutation,
} = templatesApi;
