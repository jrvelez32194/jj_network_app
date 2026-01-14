import { useState, useEffect, useMemo } from "react";
import {
  useGetTemplatesDropdownQuery,
  useAddTemplateMutation,
  useUpdateTemplateMutation,
} from "../features/api/templatesApi";

export default function SendDialog({
  isOpen,
  onClose,
  onSend,
  selectedClientIds,
}) {
  const [templateId, setTemplateId] = useState("");
  const [templateTitle, setTemplateTitle] = useState("");
  const [templateContent, setTemplateContent] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [isSending, setIsSending] = useState(false);

  // ✅ API Hooks
  const {
    data: templates = [],
    isLoading,
    isError,
  } = useGetTemplatesDropdownQuery();
  const [addTemplate] = useAddTemplateMutation();
  const [updateTemplate] = useUpdateTemplateMutation();

  // ✅ Escape key closes dialog
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // ✅ Filter templates by search term
  const filteredTemplates = useMemo(() => {
    const term = searchTerm.toLowerCase();
    return templates.filter((t) => t.title.toLowerCase().includes(term));
  }, [templates, searchTerm]);

  // ✅ Auto-select when search exactly matches template title
  useEffect(() => {
    const exactMatch = templates.find(
      (t) => t.title.toLowerCase() === searchTerm.toLowerCase()
    );
    if (exactMatch) setTemplateId(exactMatch.id.toString());
    else setTemplateId("");
  }, [searchTerm, templates]);

  // ✅ Load template content when selecting
  useEffect(() => {
    const selected = templates.find((t) => t.id === Number(templateId));
    setTemplateTitle(selected?.title || "");
    setTemplateContent(selected?.content || "");

    if (selected && searchTerm.toLowerCase() !== selected.title.toLowerCase()) {
      setSearchTerm(selected.title);
    }
  }, [templateId, templates]);

  // ✅ Send button logic aligned with backend
  const handleSend = async () => {
    if (!templateContent.trim())
      return alert("Message content cannot be empty");

    setIsSending(true);
    try {
      // Optionally create or update template
      if (templateId) {
        const original = templates.find((t) => t.id === Number(templateId));
        if (
          original &&
          (original.content !== templateContent ||
            original.title !== templateTitle)
        ) {
          await updateTemplate({
            id: Number(templateId),
            title: templateTitle || original.title,
            content: templateContent,
          }).unwrap();
        }
      } else if (templateTitle.trim()) {
        // Create new template if user provided a title
        const newTemplate = await addTemplate({
          title: templateTitle,
          content: templateContent,
        }).unwrap();
        setTemplateId(newTemplate.id.toString());
      }

      // ✅ Send to backend using title & message
      await onSend({
        title: templateTitle || "No Title",
        message: templateContent,
        client_ids: selectedClientIds.map((id) => Number(id)),
      });

      onClose();
    } catch (err) {
      console.error("Failed to send or update:", err);
      alert("Failed to send or update template.");
    } finally {
      setIsSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 bg-black/30">
      <div className="bg-white rounded-lg shadow-xl p-6 w-[500px] border animate-fadeIn max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          📤 Send Messages
        </h2>

        {/* Search and Dropdown */}
        <label className="block text-sm font-medium mb-2">
          Choose Template
        </label>
        {isLoading ? (
          <p className="text-gray-500 mb-6">Loading templates...</p>
        ) : isError ? (
          <p className="text-red-500 mb-6">Failed to load templates</p>
        ) : (
          <>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search template..."
              className="w-full border rounded-lg p-2 mb-2 focus:ring-2 focus:ring-blue-600"
            />
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="w-full border rounded-lg p-2 mb-4 focus:ring-2 focus:ring-blue-600"
              size={5}
            >
              <option value="">-- New / No Template Selected --</option>
              {filteredTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </>
        )}

        {/* Editable Template Title */}
        <label className="block text-sm font-medium mb-2">Template Title</label>
        <input
          type="text"
          value={templateTitle}
          onChange={(e) => setTemplateTitle(e.target.value)}
          placeholder="Enter template title..."
          className="w-full border rounded-lg p-2 mb-4 focus:ring-2 focus:ring-blue-600"
        />

        {/* Editable Template Content */}
        <label className="block text-sm font-medium mb-2">
          Template Content
        </label>
        <textarea
          value={templateContent}
          onChange={(e) => setTemplateContent(e.target.value)}
          placeholder="Write your message here..."
          rows={6}
          className="w-full border rounded-lg p-2 mb-4 focus:ring-2 focus:ring-blue-600"
        />

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
            disabled={isSending || !templateContent.trim()}
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
