import React from "react";

const MobileClientCards = ({
  paginatedClients,
  selectedIds,
  toggleSelection,
  renderStatus,
  renderBillingStatus,
  formatDate,
  handleDeleteClient,
  handleSetPaid,
  handleSetUnpaid,
  setEditingClient,
  setIsDrawerOpen,
}) => {
  return (
    <div className="sm:hidden flex flex-col gap-4">
      {paginatedClients.map((client) => (
        <div key={client.id} className="bg-white p-4 rounded-lg shadow border">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-semibold">{client.name}</p>
              <p className="text-sm text-gray-600">
                ID: {client.id} | Messenger: {client.messenger_id}
              </p>
              <p className="text-xs text-gray-500">
                Group: {client.group_name || "G1"}
              </p>
              <p className="text-xs text-gray-500">
                Connection: {client.connection_name || "—"}
              </p>
              <p className="text-xs mt-1 flex items-center gap-1">
                <span className="font-medium">State:</span>{" "}
                {renderStatus(client.state)}
              </p>
              <p className="text-sm text-gray-700 flex items-center gap-2">
                <span className="font-medium">Status:</span>{" "}
                {renderBillingStatus(client.status)}
              </p>
              <p className="text-xs">
                <span className="font-medium">Speed:</span>{" "}
                {client.speed_limit || "unlimited"}
              </p>
              <p className="text-xs">
                <span className="font-medium">Billing Date:</span>{" "}
                {formatDate(client.billing_date)}
              </p>
              <p className="text-xs">
                <span className="font-medium">Monthly Fee:</span>{" "}
                {client.amt_monthly != null && !isNaN(client.amt_monthly)
                  ? `₱${Number(client.amt_monthly).toFixed(2)}`
                  : "₱0.00"}
              </p>
            </div>
            <input
              type="checkbox"
              checked={selectedIds.includes(client.id)}
              onChange={() => toggleSelection(client.id)}
              className="w-4 h-4 mt-1"
            />
          </div>

          <div className="flex gap-3 mt-3 text-sm">
            <button
              onClick={() => {
                setEditingClient(client);
                setIsDrawerOpen(true);
              }}
              className="text-blue-600 hover:underline"
            >
              Edit
            </button>
            <button
              onClick={() => handleDeleteClient(client.id)}
              className="text-red-600 hover:underline"
            >
              Delete
            </button>
            <button
              onClick={() => handleSetPaid(client.id)}
              className="text-green-600 hover:underline"
            >
              Set Paid
            </button>
            <button
              onClick={() => handleSetUnpaid(client.id)}
              className="text-orange-600 hover:underline"
            >
              Set Unpaid
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MobileClientCards;
