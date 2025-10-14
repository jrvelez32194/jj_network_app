import React from "react";

const ClientToolbar = ({
  selectedIds,
  handleBulkDelete,
  handleBulkSetPaid,
  handleBulkSetUnpaid,
  handleOpenSend,
  handleSyncClients,
  isSyncing,
  setEditingClient,
  setIsDrawerOpen,
}) => {
  const hasSelection = selectedIds.length > 0;

  const baseButton =
    "px-4 py-2 rounded transition-all duration-150 disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-600";

  return (
    <div className="hidden sm:flex justify-between items-center mb-4">
      <div className="space-x-2 flex items-center">
        {/* 🗑 Delete */}
        <button
          onClick={handleBulkDelete}
          disabled={!hasSelection}
          className={`${baseButton} ${
            hasSelection
              ? "bg-red-600 text-white hover:bg-red-700"
              : "bg-gray-300 text-gray-600"
          }`}
        >
          🗑 Delete {hasSelection && `(${selectedIds.length})`}
        </button>

        {/* 💰 Set Paid */}
        <button
          onClick={handleBulkSetPaid}
          disabled={!hasSelection}
          className={`${baseButton} ${
            hasSelection
              ? "bg-yellow-600 text-white hover:bg-yellow-700"
              : "bg-gray-300 text-gray-600"
          }`}
        >
          💰 Set Paid {hasSelection && `(${selectedIds.length})`}
        </button>

        {/* ❌ Set Unpaid */}
        <button
          onClick={handleBulkSetUnpaid}
          disabled={!hasSelection}
          className={`${baseButton} ${
            hasSelection
              ? "bg-orange-600 text-white hover:bg-orange-700"
              : "bg-gray-300 text-gray-600"
          }`}
        >
          ❌ Set Unpaid {hasSelection && `(${selectedIds.length})`}
        </button>

        {/* 📤 Send */}
        <button
          onClick={handleOpenSend}
          disabled={!hasSelection}
          className={`${baseButton} ${
            hasSelection
              ? "bg-green-600 text-white hover:bg-green-700"
              : "bg-gray-300 text-gray-600"
          }`}
        >
          📤 Send {hasSelection && `(${selectedIds.length})`}
        </button>

        {/* 🔄 Sync Clients */}
        <button
          onClick={handleSyncClients}
          disabled={isSyncing}
          className={`${baseButton} bg-purple-600 text-white hover:bg-purple-700`}
        >
          {isSyncing ? "⏳ Syncing..." : "🔄 Sync Clients"}
        </button>
      </div>

      {/* ➕ Add Client */}
      <button
        onClick={() => {
          setEditingClient(null);
          setIsDrawerOpen(true);
        }}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        ➕ Add Client
      </button>
    </div>
  );
};

export default ClientToolbar;
