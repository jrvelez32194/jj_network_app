import { useState, useEffect } from "react";

export default function AddTemplateDrawer({
  isOpen,
  onClose,
  onSave,
  editingTemplate,
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // ✅ Fill form when editing OR reset when adding new
  useEffect(() => {
    if (editingTemplate) {
      setTitle(editingTemplate.title || "");
      setContent(editingTemplate.content || "");
    } else {
      setTitle("");
      setContent("");
    }
  }, [editingTemplate, isOpen]);

  // ✅ Close drawer with ESC
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleEsc);
    }
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen]);

  const handleClose = () => {
    setTitle("");
    setContent("");
    setIsSaving(false);
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);

    const success = await onSave({ title, content });

    if (success) {
      handleClose(); // ✅ reset + close drawer
    } else {
      setIsSaving(false); // keep form open if failed
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex sm:items-stretch">
      {/* Overlay */}
      <div className="flex-1 bg-black/40" onClick={handleClose} />

      {/* Drawer (desktop) / Bottom Sheet (mobile) */}
      <div
        className="
          w-full bg-white shadow-xl flex flex-col
          sm:ml-auto sm:max-w-md sm:h-full sm:rounded-l-2xl 
          sm:animate-slideInRight
          animate-slideInUp
          rounded-t-2xl
        "
        onClick={(e) => e.stopPropagation()} // prevent closing inside
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-800">
            {editingTemplate ? "✏️ Edit Template" : "➕ Add Template"}
          </h3>
          <button
            onClick={handleClose}
            className="text-gray-500 hover:text-gray-800 transition"
          >
            ✕
          </button>
        </div>

        {/* Form */}
        <div className="p-6 flex-1 overflow-y-auto">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Content
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full border p-3 rounded-lg h-40 resize-none focus:ring-2 focus:ring-blue-600"
                required
              />
            </div>

            <button
              type="submit"
              disabled={!title || !content || isSaving}
              className={`w-full py-3 font-semibold rounded-lg shadow transition ${
                !title || !content || isSaving
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
            >
              {isSaving
                ? "Saving..."
                : editingTemplate
                ? "Update Template"
                : "Save Template"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
