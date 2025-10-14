import React from "react";
import { MoreVertical } from "lucide-react";

const FloatingActionMenu = ({
  fabOpen,
  setFabOpen,
  selectedIds,
  handleBulkDelete,
  handleBulkSetPaid,
  handleBulkSetUnpaid,
  handleOpenSend,
  handleSyncClients,
  setEditingClient,
  setIsDrawerOpen,
}) => {
  const isDisabled = selectedIds.length === 0;

  return (
    <div className="sm:hidden fixed bottom-6 right-6 flex flex-col items-end space-y-2 z-50">
      {/* ✅ FAB Actions */}
      {fabOpen && (
        <div className="flex flex-col items-end space-y-2 mb-2 transition-all duration-300">
          {/* Delete */}
          <button
            onClick={() => {
              handleBulkDelete();
              setFabOpen(false);
            }}
            disabled={isDisabled}
            className={`p-3 rounded-full shadow-lg text-white ${
              isDisabled
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-red-600 hover:bg-red-700"
            }`}
          >
            🗑 Delete
          </button>

          {/* Paid */}
          <button
            onClick={() => {
              handleBulkSetPaid();
              setFabOpen(false);
            }}
            disabled={isDisabled}
            className={`p-3 rounded-full shadow-lg text-white ${
              isDisabled
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-yellow-600 hover:bg-yellow-700"
            }`}
          >
            💰 Set Paid
          </button>

          {/* Unpaid */}
          <button
            onClick={() => {
              handleBulkSetUnpaid();
              setFabOpen(false);
            }}
            disabled={isDisabled}
            className={`p-3 rounded-full shadow-lg text-white ${
              isDisabled
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-orange-600 hover:bg-orange-700"
            }`}
          >
            ❌ Set Unpaid
          </button>

          {/* Send Messenger */}
          <button
            onClick={() => {
              handleOpenSend();
              setFabOpen(false);
            }}
            disabled={isDisabled}
            className={`p-3 rounded-full shadow-lg text-white ${
              isDisabled
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-green-600 hover:bg-green-700"
            }`}
          >
            📤 Send Messenger
          </button>

          {/* Sync */}
          <button
            onClick={() => {
              handleSyncClients();
              setFabOpen(false);
            }}
            className="p-3 rounded-full shadow-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            🔄 Sync from Messenger
          </button>

          {/* Add Client */}
          <button
            onClick={() => {
              setEditingClient(null);
              setIsDrawerOpen(true);
              setFabOpen(false);
            }}
            className="p-3 rounded-full shadow-lg bg-indigo-600 text-white hover:bg-indigo-700"
          >
            ➕ Add Client
          </button>
        </div>
      )}

      {/* ✅ FAB Toggle Button */}
      <button
        onClick={() => setFabOpen(!fabOpen)}
        className="p-4 rounded-full bg-purple-600 text-white shadow-xl hover:bg-purple-700 transition-transform transform hover:scale-105"
      >
        <MoreVertical className="w-6 h-6" />
      </button>
    </div>
  );
};

export default FloatingActionMenu;
