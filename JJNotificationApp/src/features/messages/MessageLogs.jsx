import { useState, useMemo, useEffect } from "react";
import {
  useGetMessageLogsQuery,
  useDeleteMessageLogMutation,
  useDeleteMessageLogsMutation,
  useDeleteAllMessageLogsMutation,
} from "../api/messageLogsApi";
import ConfirmDialog from "../../components/ConfirmDialog";
import { InfoDialog } from "../../components/InfoDialog";
import Pagination from "../../components/Pagination";

export default function MessageLogs() {
  const { showToast, Toast } = InfoDialog();

  // ✅ Selection state
  const [selectedIds, setSelectedIds] = useState([]);
  const [allSelected, setAllSelected] = useState(false);

  const toggleSelection = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSelectAllPage = (checked, pageLogs) => {
    if (checked) {
      const newIds = [
        ...new Set([...selectedIds, ...pageLogs.map((l) => l.id)]),
      ];
      setSelectedIds(newIds);
    } else {
      setSelectedIds(
        selectedIds.filter((id) => !pageLogs.find((l) => l.id === id))
      );
      setAllSelected(false);
    }
  };

  const handleSelectAllAcrossPages = (logs) => {
    setSelectedIds(logs.map((l) => l.id));
    setAllSelected(true);
  };

  const clearAllSelection = () => {
    setSelectedIds([]);
    setAllSelected(false);
  };

  // ✅ Filters/Search
  const [searchTerm, setSearchTerm] = useState("");
  const handleSearch = (value) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  // ✅ Fetch logs
  const {
    data: logs = [],
    isLoading,
    isError,
  } = useGetMessageLogsQuery(undefined, { pollingInterval: 10000 });

  const [deleteMessageLog] = useDeleteMessageLogMutation();
  const [deleteMessageLogs] = useDeleteMessageLogsMutation();
  const [deleteAllMessageLogs] = useDeleteAllMessageLogsMutation();

  // ✅ Filtered logs
  const filteredLogs = useMemo(() => {
    const term = searchTerm.toLowerCase();
    return logs.filter((log) => {
      return (
        !searchTerm ||
        log.title?.toLowerCase().includes(term) ||
        log.message?.toLowerCase().includes(term) ||
        log.status?.toLowerCase().includes(term)
      );
    });
  }, [logs, searchTerm]);

  // ✅ Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;
  const totalPages = Math.ceil(filteredLogs.length / pageSize);
  const currentPageSafe = Math.min(currentPage, totalPages || 1);
  const paginatedLogs = filteredLogs.slice(
    (currentPageSafe - 1) * pageSize,
    currentPageSafe * pageSize
  );

  useEffect(() => {
    const savedPage = Number(localStorage.getItem("messageLogsPage")) || 1;
    setCurrentPage(savedPage);
  }, []);

  useEffect(() => {
    localStorage.setItem("messageLogsPage", currentPage);
  }, [currentPage]);

  // ✅ Delete confirmation
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmMessage, setConfirmMessage] = useState("");

  const handleDeleteSingle = (id) => {
    setConfirmMessage("Are you sure you want to delete this log?");
    setConfirmAction(() => async () => {
      try {
        await deleteMessageLog(id).unwrap();
        showToast("Log deleted ✅");
        setSelectedIds((prev) => prev.filter((x) => x !== id));
        return true;
      } catch {
        showToast("Failed to delete ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  const handleBulkDelete = () => {
    if (selectedIds.length === 0) return;
    setConfirmMessage(
      `Are you sure you want to delete ${selectedIds.length} logs?`
    );
    setConfirmAction(() => async () => {
      try {
        await deleteMessageLogs(selectedIds).unwrap();
        showToast(`Deleted ${selectedIds.length} logs ✅`);
        clearAllSelection();
        return true;
      } catch {
        showToast("Failed to delete ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  const handleClearAllLogs = () => {
    setConfirmMessage("⚠️ Are you sure you want to delete ALL message logs?");
    setConfirmAction(() => async () => {
      try {
        await deleteAllMessageLogs(true).unwrap();
        showToast("All message logs cleared 🧹");
        clearAllSelection();
        return true;
      } catch {
        showToast("Failed to clear all logs ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <h1 className="text-xl font-bold mb-4">📊 Message Logs</h1>

      {/* ✅ Search */}
      <div className="mb-4">
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
            placeholder="Search by title, message, or status..."
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

      {/* ✅ Toolbar */}
      <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
        <div className="space-x-2 flex items-center flex-wrap">
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

          <button
            onClick={handleClearAllLogs}
            className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
          >
            🧹 Clear All Logs
          </button>

          {selectedIds.length > 0 && !allSelected && (
            <button
              onClick={() => handleSelectAllAcrossPages(logs)}
              className="px-3 py-2 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              Select all {logs.length} logs
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
                    paginatedLogs.every((l) => selectedIds.includes(l.id)) &&
                    paginatedLogs.length > 0
                  }
                  onChange={(e) =>
                    handleSelectAllPage(e.target.checked, paginatedLogs)
                  }
                />
              </th>
              <th className="px-6 py-3">ID</th>
              <th className="px-6 py-3">Title</th>
              <th className="px-6 py-3">Message</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Created At</th>
              <th className="px-6 py-3">Sent At</th>
              <th className="px-6 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan="8" className="p-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan="8" className="p-6 text-center text-red-500">
                  Error loading logs.
                </td>
              </tr>
            ) : paginatedLogs.length === 0 ? (
              <tr>
                <td colSpan="8" className="p-6 text-center text-gray-500">
                  No logs found.
                </td>
              </tr>
            ) : (
              paginatedLogs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 w-12 text-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(log.id)}
                      onChange={() => toggleSelection(log.id)}
                      className="w-4 h-4 align-middle"
                    />
                  </td>
                  <td className="px-6 py-4">{log.id}</td>
                  <td className="px-6 py-4 font-semibold">{log.title}</td>
                  <td
                    className="px-6 py-4 max-w-md truncate"
                    title={log.message}
                  >
                    {log.message}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        log.status === "sent"
                          ? "bg-green-100 text-green-700"
                          : log.status === "failed"
                          ? "bg-red-100 text-red-700"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    {log.sent_at ? new Date(log.sent_at).toLocaleString() : "-"}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleDeleteSingle(log.id)}
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

      {/* ✅ Mobile Card View */}
      <div className="block sm:hidden space-y-4">
        {paginatedLogs.map((log) => (
          <div
            key={log.id}
            className="bg-white rounded-lg shadow p-4 border border-gray-200"
          >
            <div className="flex justify-between">
              <div>
                <p className="font-semibold">{log.title}</p>
                <p className="text-sm text-gray-600 break-words">
                  {log.message}
                </p>
                <p className="text-xs mt-2">
                  Status: <span className="font-semibold">{log.status}</span>
                </p>
                <p className="text-xs text-gray-500">
                  Created: {new Date(log.created_at).toLocaleString()}
                </p>
                <p className="text-xs text-gray-500">
                  Sent:{" "}
                  {log.sent_at ? new Date(log.sent_at).toLocaleString() : "-"}
                </p>
              </div>
              <input
                type="checkbox"
                checked={selectedIds.includes(log.id)}
                onChange={() => toggleSelection(log.id)}
                className="w-4 h-4 mt-1"
              />
            </div>
            <button
              onClick={() => handleDeleteSingle(log.id)}
              className="mt-3 text-sm text-red-600 hover:underline"
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      {/* ✅ Global Pagination */}
      <Pagination
        totalItems={filteredLogs.length}
        pageSize={pageSize}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />

      {/* ✅ Confirm Dialog */}
      <ConfirmDialog
        isOpen={confirmOpen}
        title="Confirm Deletion"
        message={confirmMessage}
        onClose={() => setConfirmOpen(false)}
        onConfirm={async () => {
          if (confirmAction) {
            const success = await confirmAction();
            if (success) setConfirmOpen(false);
          } else {
            setConfirmOpen(false);
          }
        }}
      />

      <Toast />
    </div>
  );
}
