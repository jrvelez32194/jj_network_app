import { useState, useMemo, useEffect } from "react";
import {
  useGetTemplatesQuery,
  useAddTemplateMutation,
  useUpdateTemplateMutation,
  useDeleteTemplateMutation,
  useDeleteTemplatesMutation,
} from "../templates/templatesApi";
import AddTemplateDrawer from "./AddTemplateDrawer";
import ConfirmDialog from "../../components/ConfirmDialog";
import { UseToast } from "../../components/UseToast";
import Pagination from "../../components/common/Pagination";

const TemplatesPage = () => {
  // ✅ State
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmMessage, setConfirmMessage] = useState("");

  const { data: templates = [], isLoading } = useGetTemplatesQuery();
  const [addTemplate] = useAddTemplateMutation();
  const [updateTemplate] = useUpdateTemplateMutation();
  const [deleteTemplate] = useDeleteTemplateMutation();
  const [deleteTemplates] = useDeleteTemplatesMutation();

  const { showToast, Toast } = UseToast();

  // ✅ Selection
  const [selectedIds, setSelectedIds] = useState([]);
  const [allSelected, setAllSelected] = useState(false);

  const toggleSelection = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSelectAllPage = (checked, pageTemplates) => {
    if (checked) {
      const newIds = [
        ...new Set([...selectedIds, ...pageTemplates.map((t) => t.id)]),
      ];
      setSelectedIds(newIds);
    } else {
      const newIds = selectedIds.filter(
        (id) => !pageTemplates.find((t) => t.id === id)
      );
      setSelectedIds(newIds);
      setAllSelected(false);
    }
  };

  const handleSelectAllAcrossPages = () => {
    setSelectedIds(templates.map((t) => t.id));
    setAllSelected(true);
  };

  const clearAllSelection = () => {
    setSelectedIds([]);
    setAllSelected(false);
  };

  // ✅ Search
  const [searchTerm, setSearchTerm] = useState("");
  const filteredTemplates = useMemo(() => {
    if (!searchTerm) return templates;
    return templates.filter(
      (t) =>
        t.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.content?.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [templates, searchTerm]);

  // ✅ Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // ✅ Reset only on search
  useMemo(() => {
    setCurrentPage(1);
  }, [searchTerm]);

  // ✅ Safe pagination
  const totalPages = Math.ceil(filteredTemplates.length / pageSize);
  const currentPageSafe = Math.min(currentPage, totalPages || 1);
  const paginatedTemplates = filteredTemplates.slice(
    (currentPageSafe - 1) * pageSize,
    currentPageSafe * pageSize
  );

  useEffect(() => {
    const savedPage = Number(localStorage.getItem("clientTempalate")) || 1;
    setCurrentPage(savedPage);
  }, []);

  useEffect(() => {
    localStorage.setItem("clientTempalate", currentPage);
  }, [currentPage]);

  const handleSearch = (value) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  // ✅ Save template
  const handleSaveTemplate = async (templateData) => {
    try {
      if (editingTemplate) {
        await updateTemplate({
          id: editingTemplate.id,
          ...templateData,
        }).unwrap();
        showToast("Template updated ✅");
      } else {
        await addTemplate(templateData).unwrap();
        showToast("Template added ✅");
      }
      setIsDrawerOpen(false);
      setEditingTemplate(null);
    } catch (err) {
      console.error("Failed to save template:", err);
      showToast(err?.data?.detail || "Something went wrong ❌", "error");
    }
  };

  // ✅ Delete single
  const handleDeleteTemplate = (id) => {
    setConfirmMessage("Are you sure you want to delete this template?");
    setConfirmAction(() => async () => {
      try {
        await deleteTemplate(id).unwrap();
        showToast("Template deleted ✅");
        return true;
      } catch {
        showToast("Failed to delete ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  // ✅ Bulk delete
  const handleBulkDelete = () => {
    if (selectedIds.length === 0) return;
    setConfirmMessage(
      `Are you sure you want to delete ${selectedIds.length} templates?`
    );
    setConfirmAction(() => async () => {
      try {
        await deleteTemplates(selectedIds).unwrap();
        showToast(`Deleted ${selectedIds.length} templates ✅`);
        clearAllSelection();
        return true;
      } catch {
        showToast("Failed to delete ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Templates</h1>

      {/* ✅ Search */}
      <div className="mb-6">
        <div className="flex items-center bg-gray-100 rounded-lg px-3 py-2 shadow-sm">
          <svg
            className="w-5 h-5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search templates..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            className="flex-1 bg-transparent outline-none px-2"
          />
          {searchTerm && (
            <button
              onClick={() => handleSearch("")}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ✅ Toolbar (Desktop) */}
      <div className="hidden sm:flex justify-between items-center mb-4">
        <div className="space-x-2 flex items-center">
          <button
            onClick={handleBulkDelete}
            disabled={selectedIds.length === 0}
            className={`px-4 py-2 rounded ${
              selectedIds.length === 0
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-red-600 text-white hover:bg-red-700"
            }`}
          >
            🗑 Delete {selectedIds.length > 0 && `(${selectedIds.length})`}
          </button>

          {/* ✅ Select Across Pages */}
          {selectedIds.length > 0 && !allSelected && (
            <button
              onClick={handleSelectAllAcrossPages}
              className="px-3 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              Select all {templates.length} templates
            </button>
          )}
          {allSelected && (
            <button
              onClick={clearAllSelection}
              className="px-3 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              Clear selection
            </button>
          )}
        </div>
        <button
          onClick={() => {
            setEditingTemplate(null);
            setIsDrawerOpen(true);
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          ➕ Add Template
        </button>
      </div>

      {/* ✅ Desktop Table */}
      <div className="hidden sm:block overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold">
            <tr>
              <th className="px-6 py-3 w-12 text-center">
                <input
                  type="checkbox"
                  checked={
                    paginatedTemplates.every((t) =>
                      selectedIds.includes(t.id)
                    ) && paginatedTemplates.length > 0
                  }
                  onChange={(e) =>
                    handleSelectAllPage(e.target.checked, paginatedTemplates)
                  }
                  className="w-4 h-4 align-middle"
                />
              </th>
              <th className="px-6 py-3">ID</th>
              <th className="px-6 py-3">Title</th>
              <th className="px-6 py-3">Content</th>
              <th className="px-6 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan="5" className="p-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            ) : paginatedTemplates.length === 0 ? (
              <tr>
                <td colSpan="5" className="p-6 text-center text-gray-500">
                  No templates found.
                </td>
              </tr>
            ) : (
              paginatedTemplates.map((template) => (
                <tr key={template.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 w-12 text-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(template.id)}
                      onChange={() => toggleSelection(template.id)}
                      className="w-4 h-4 align-middle"
                    />
                  </td>
                  <td className="px-6 py-4">{template.id}</td>
                  <td className="px-6 py-4">{template.title}</td>
                  <td className="px-6 py-4 truncate max-w-xs">
                    {template.content}
                  </td>
                  <td className="px-6 py-4 space-x-2">
                    <button
                      onClick={() => {
                        setEditingTemplate(template);
                        setIsDrawerOpen(true);
                      }}
                      className="text-blue-600 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteTemplate(template.id)}
                      className="text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ✅ Mobile Toolbar + Select All */}
      <div className="sm:hidden flex flex-col gap-3 mb-4">
        <div className="flex justify-between items-center">
          <button
            onClick={handleBulkDelete}
            disabled={selectedIds.length === 0}
            className={`px-3 py-2 rounded text-sm ${
              selectedIds.length === 0
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-red-600 text-white hover:bg-red-700"
            }`}
          >
            🗑 Delete {selectedIds.length > 0 && `(${selectedIds.length})`}
          </button>
          {/* 🚫 Removed mobile Add button (FAB replaces this) */}
        </div>

        <div className="flex items-center gap-2 bg-gray-100 px-3 py-2 rounded shadow-sm">
          <input
            type="checkbox"
            checked={
              paginatedTemplates.every((t) => selectedIds.includes(t.id)) &&
              paginatedTemplates.length > 0
            }
            onChange={(e) =>
              handleSelectAllPage(e.target.checked, paginatedTemplates)
            }
            className="w-4 h-4"
          />
          <span className="text-sm text-gray-700">Select all on this page</span>
        </div>

        {/* ✅ Select All Across Pages */}
        {selectedIds.length > 0 && !allSelected && (
          <button
            onClick={handleSelectAllAcrossPages}
            className="px-3 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
          >
            Select all {templates.length} templates
          </button>
        )}
        {allSelected && (
          <button
            onClick={clearAllSelection}
            className="px-3 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
          >
            Clear selection
          </button>
        )}
      </div>

      {/* ✅ Mobile Card View */}
      <div className="block sm:hidden space-y-4">
        {isLoading ? (
          <p className="text-center text-gray-500">Loading...</p>
        ) : paginatedTemplates.length === 0 ? (
          <p className="text-center text-gray-500">No templates found.</p>
        ) : (
          paginatedTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-lg shadow p-4 border border-gray-200"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-semibold">{template.title}</p>
                  <p className="text-sm text-gray-600">ID: {template.id}</p>
                  <p className="text-sm text-gray-600 truncate max-w-[200px]">
                    {template.content}
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={selectedIds.includes(template.id)}
                  onChange={() => toggleSelection(template.id)}
                  className="w-4 h-4 mt-1"
                />
              </div>
              <div className="flex gap-3 mt-3 text-sm">
                <button
                  onClick={() => {
                    setEditingTemplate(template);
                    setIsDrawerOpen(true);
                  }}
                  className="text-blue-600 hover:underline"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDeleteTemplate(template.id)}
                  className="text-red-600 hover:underline"
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* ✅ Floating Add Template Button (Mobile Only) */}
      <div className="sm:hidden fixed bottom-20 right-6 flex flex-col items-end space-y-2 z-50">
        <button
          onClick={() => {
            setEditingTemplate(null);
            setIsDrawerOpen(true);
          }}
          className="w-14 h-14 flex items-center justify-center rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700 transition"
        >
          ➕
        </button>
      </div>

      {/* ✅ Global Pagination */}
      <Pagination
        totalItems={filteredTemplates.length}
        pageSize={pageSize}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />

      {/* ✅ Modals */}
      <AddTemplateDrawer
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setEditingTemplate(null);
        }}
        onSave={handleSaveTemplate}
        editingTemplate={editingTemplate}
      />

      <ConfirmDialog
        isOpen={confirmOpen}
        message={confirmMessage}
        onClose={() => setConfirmOpen(false)}
        onConfirm={async () => {
          if (confirmAction) await confirmAction();
          setConfirmOpen(false);
        }}
      />

      <Toast />
    </div>
  );
};

export default TemplatesPage;
