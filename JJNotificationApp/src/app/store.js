// src/app/store.js
import { configureStore } from "@reduxjs/toolkit";
import { apiSlice } from "../features/api/apiSlice"; // base slice

export const store = configureStore({
  reducer: {
    [apiSlice.reducerPath]: apiSlice.reducer, // only once
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(apiSlice.middleware), // only once
});
