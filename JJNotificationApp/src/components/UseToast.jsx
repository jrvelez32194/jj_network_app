import { useState } from "react";

export function UseToast() {
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const Toast = () =>
    toast ? (
      <div
        className={`fixed bottom-6 right-6 px-4 py-2 rounded shadow-lg text-white ${
          toast.type === "success" ? "bg-green-600" : "bg-red-600"
        }`}
      >
        {toast.message}
      </div>
    ) : null;

  return { showToast, Toast };
}
