import { useEffect, useState } from "react";

export default function AddClientDrawer({
  isOpen,
  onClose,
  onSave,
  editingClient,
  onSetPaid,
}) {
  const [name, setName] = useState("");
  const [messengerId, setMessengerId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [connectionName, setConnectionName] = useState("");
  const [billingDate, setBillingDate] = useState("");
  const [amtMonthly, setAmtMonthly] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (editingClient) {
      setName(editingClient.name || "");
      setMessengerId(editingClient.messenger_id || "");
      setGroupName(editingClient.group_name || "");
      setConnectionName(editingClient.connection_name || "");
      setBillingDate(editingClient.billing_date || "");
      setAmtMonthly(editingClient.amt_monthly || "");
    } else {
      setName("");
      setMessengerId("");
      setGroupName("");
      setConnectionName("");
      setBillingDate("");
      setAmtMonthly("");
    }
  }, [editingClient, isOpen]);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") handleClose();
    };
    if (isOpen) window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen]);

  const handleClose = () => {
    setName("");
    setMessengerId("");
    setGroupName("");
    setConnectionName("");
    setBillingDate("");
    setAmtMonthly("");
    setIsSaving(false);
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);

    const payload = {
      name,
      messenger_id: messengerId,
      group_name: groupName || null,
      connection_name: connectionName || null,
      billing_date: billingDate?.trim() || null, // ✅ optional
      amt_monthly: amtMonthly ? parseFloat(amtMonthly) : null, // ✅ optional
    };

    const success = await onSave(payload);

    if (success) handleClose();
    else setIsSaving(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex sm:items-stretch">
      <div className="flex-1 bg-black/40" onClick={handleClose} />

      <div
        className="
          w-full bg-white shadow-xl flex flex-col 
          sm:ml-auto sm:max-w-md sm:h-full sm:rounded-l-2xl 
          sm:animate-slideInRight animate-slideInUp
          rounded-t-2xl
        "
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-800">
            {editingClient ? "✏️ Edit Client" : "➕ Add Client"}
          </h3>
          <button
            onClick={handleClose}
            className="text-gray-500 hover:text-gray-800 transition"
          >
            ✕
          </button>
        </div>

        <div className="p-6 flex-1 overflow-y-auto">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
                required
              />
            </div>

            {/* Messenger ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Messenger ID
              </label>
              <input
                type="text"
                value={messengerId}
                onChange={(e) => setMessengerId(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
                required
              />
            </div>

            {/* Group Name (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Group (optional)
              </label>
              <input
                type="text"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* Connection Name (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Connection (optional)
              </label>
              <input
                type="text"
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* Billing Date (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Billing Date (optional)
              </label>
              <input
                type="date"
                value={billingDate}
                onChange={(e) => setBillingDate(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* Monthly Amount (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Monthly Amount (₱, optional)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={amtMonthly}
                onChange={(e) => setAmtMonthly(e.target.value)}
                className="w-full border p-3 rounded-lg focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={!name || !messengerId || isSaving}
              className={`w-full py-3 font-semibold rounded-lg shadow transition ${
                !name || !messengerId || isSaving
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
            >
              {isSaving
                ? "Saving..."
                : editingClient
                ? "Update Client"
                : "Save Client"}
            </button>
          </form>

          {/* Set Paid Button */}
          {editingClient && (
            <button
              onClick={() => onSetPaid(editingClient)}
              className="mt-4 w-full py-3 font-semibold rounded-lg shadow bg-green-600 text-white hover:bg-green-700"
            >
              💵 Set Paid
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
