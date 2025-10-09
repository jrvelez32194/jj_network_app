import { useState, useEffect } from "react";
import { useGetTemplatesDropdownQuery } from "../features/templates/templatesApi";

export default function SendDialog({
  isOpen,
  onClose,
  onSend,
  selectedClientIds,
}) {
  const [templateId, setTemplateId] = useState("");
  const [isSending, setIsSending] = useState(false);

  // ✅ Escape key handler
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Fetch templates for dropdown
  const {
    data: templates = [],
    isLoading,
    isError,
  } = useGetTemplatesDropdownQuery();

  const handleSend = async () => {
    if (!templateId) return;

    setIsSending(true);
    try {
      await onSend(Number(templateId), selectedClientIds); // ✅ send both values
      onClose(); // ✅ close after success
    } catch (err) {
      console.error("Failed to send:", err);
    } finally {
      setIsSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 bg-black/30">
      {/* Dialog panel */}
      <div className="bg-white rounded-lg shadow-xl p-6 w-[400px] border animate-fadeIn">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          📤 Send Messages
        </h2>

        <label className="block text-sm font-medium mb-2">
          Choose Template
        </label>

        {isLoading ? (
          <p className="text-gray-500 mb-6">Loading templates...</p>
        ) : isError ? (
          <p className="text-red-500 mb-6">Failed to load templates</p>
        ) : (
          <select
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            className="w-full border rounded-lg p-2 mb-6 focus:ring-2 focus:ring-blue-600"
          >
            <option value="">-- Select a template --</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isSending}
            className="px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={!templateId || isSending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isSending ? (
              <>
                <svg
                  className="w-4 h-4 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  ></path>
                </svg>
                Sending...
              </>
            ) : (
              "Send"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
