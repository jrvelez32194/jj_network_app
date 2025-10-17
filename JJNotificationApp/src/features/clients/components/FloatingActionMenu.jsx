import React from "react";
import { MoreVertical } from "lucide-react";
import {
  useNotifyClientMutation,
  useNotifyAllClientsMutation,
} from "../../api/forceBillingApi";

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

  // 🧠 RTK Mutations
  const [notifyClient, { isLoading: isNotifyingClient }] =
    useNotifyClientMutation();
  const [notifyAllClients, { isLoading: isNotifyingAll }] =
    useNotifyAllClientsMutation();

  // 💬 Notify Selected Clients (Billing)
  const handleNotifySelectedBilling = async () => {
    if (isDisabled) return;
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
      alert("❌ Failed to send billing notifications.");
    } finally {
      setFabOpen(false);
    }
  };

  // 📢 Notify All Clients
  const handleNotifyAllBilling = async () => {
    if (!window.confirm("Send billing notification to ALL clients?")) return;
    try {
      await notifyAllClients().unwrap();
      alert("✅ Billing notifications sent to all clients!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to send billing notifications to all clients.");
    } finally {
      setFabOpen(false);
    }
  };

  return (
    <div className="sm:hidden fixed bottom-6 right-6 flex flex-col items-end space-y-2 z-50">
      {/* ✅ FAB Actions */}
      {fabOpen && (
        <div className="flex flex-col items-end space-y-2 mb-2 transition-all duration-300">
          {/* 🗑 Delete */}
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

          {/* 💰 Set Paid */}
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

          {/* ❌ Set Unpaid */}
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

          {/* 📤 Send Messenger */}
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

          {/* 💬 Notify Billing (Selected) */}
          <button
            onClick={handleNotifySelectedBilling}
            disabled={isDisabled || isNotifyingClient}
            className={`p-3 rounded-full shadow-lg text-white ${
              isDisabled
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700"
            }`}
          >
            {isNotifyingClient ? "⏳ Notifying..." : "💬 Notify Billing"}
          </button>

          {/* 📢 Notify All Billing */}
          <button
            onClick={handleNotifyAllBilling}
            disabled={isNotifyingAll}
            className={`p-3 rounded-full shadow-lg text-white bg-blue-600 hover:bg-blue-700`}
          >
            {isNotifyingAll ? "⏳ Notifying..." : "📢 Notify All"}
          </button>

          {/* 🔄 Sync */}
          <button
            onClick={() => {
              handleSyncClients();
              setFabOpen(false);
            }}
            className="p-3 rounded-full shadow-lg bg-purple-600 text-white hover:bg-purple-700"
          >
            🔄 Sync
          </button>

          {/* ➕ Add Client */}
          <button
            onClick={() => {
              setEditingClient(null);
              setIsDrawerOpen(true);
              setFabOpen(false);
            }}
            className="p-3 rounded-full shadow-lg bg-teal-600 text-white hover:bg-teal-700"
          >
            ➕ Add Client
          </button>
        </div>
      )}

      {/* ✅ FAB Toggle */}
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
