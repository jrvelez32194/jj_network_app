import React from "react";
import {
  useNotifyClientMutation,
  useNotifyAllClientsMutation,
} from "../../api/forceBillingApi";

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
  const countLabel = hasSelection ? `(${selectedIds.length})` : "";

  const baseButton =
    "min-w-[130px] px-4 py-2 rounded transition-all duration-150 flex items-center justify-center gap-1 text-sm sm:text-base disabled:cursor-not-allowed disabled:bg-gray-300 disabled:text-gray-600";

  // 🧠 RTK mutations
  const [notifyClient, { isLoading: isNotifyingClient }] =
    useNotifyClientMutation();
  const [notifyAllClients, { isLoading: isNotifyingAll }] =
    useNotifyAllClientsMutation();

  const handleNotifySelectedBilling = async () => {
    if (!hasSelection) return;
    if (
      !window.confirm(
        `Send billing notification to ${selectedIds.length} client(s)?`
      )
    )
      return;
    try {
      for (const id of selectedIds) {
        await notifyClient(id).unwrap();
      }
      alert("✅ Billing notifications sent successfully!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to send one or more billing notifications.");
    }
  };

  const handleNotifyAllBilling = async () => {
    if (!window.confirm("Send billing notification to ALL clients?")) return;
    try {
      await notifyAllClients().unwrap();
      alert("✅ Billing notifications sent to all clients!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to send billing notifications to all clients.");
    }
  };

  return (
    <div className="hidden sm:flex flex-wrap justify-between items-center gap-2 mb-4">
      <div className="flex flex-wrap gap-2 items-center">
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
          🗑 Delete <span className="invisible sm:visible">{countLabel}</span>
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
          💰 Set Paid <span className="invisible sm:visible">{countLabel}</span>
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
          ❌ Set Unpaid{" "}
          <span className="invisible sm:visible">{countLabel}</span>
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
          📤 Send <span className="invisible sm:visible">{countLabel}</span>
        </button>

        {/* 💬 Notify Billing */}
        <button
          onClick={handleNotifySelectedBilling}
          disabled={!hasSelection || isNotifyingClient}
          className={`${baseButton} ${
            hasSelection
              ? "bg-indigo-600 text-white hover:bg-indigo-700"
              : "bg-gray-300 text-gray-600"
          }`}
        >
          {isNotifyingClient ? "⏳ Notifying..." : `💬 Notify Billing `}
          <span className="invisible sm:visible">{countLabel}</span>
        </button>

        {/* 🌐 Notify All Billing */}
        <button
          onClick={handleNotifyAllBilling}
          disabled={isNotifyingAll}
          className={`${baseButton} bg-blue-600 text-white hover:bg-blue-700`}
        >
          {isNotifyingAll ? "⏳ Notifying..." : "📢 Notify All"}
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
