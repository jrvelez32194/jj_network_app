import React from "react";

const ClientTable = ({
  paginatedClients,
  selectedIds,
  isLoading,
  handleSelectAllPage,
  toggleSelection,
  handleDeleteClient,
  handleSetPaid,
  handleSetUnpaid,
  renderStatus,
  renderBillingStatus,
  formatDate,
  setEditingClient,
  setIsDrawerOpen,
}) => {
  return (
    <div className="hidden sm:block overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold">
          <tr>
            <th className="px-6 py-3 w-12 text-center">
              <input
                type="checkbox"
                checked={
                  paginatedClients.length > 0 &&
                  paginatedClients.every((c) => selectedIds.includes(c.id))
                }
                onChange={(e) =>
                  handleSelectAllPage(e.target.checked, paginatedClients)
                }
                className="w-4 h-4"
              />
            </th>
            <th className="px-6 py-3">ID</th>
            <th className="px-6 py-3">Name</th>
            <th className="px-6 py-3">Messenger ID</th>
            <th className="px-6 py-3">Group</th>
            <th className="px-6 py-3">Connection</th>
            <th className="px-6 py-3">State</th>
            <th className="px-6 py-3">Status</th>
            <th className="px-6 py-3">Speed</th>
            <th className="px-6 py-3">Billing Date</th>
            <th className="px-6 py-3">Monthly Fee</th>
            <th className="px-6 py-3 min-w-[180px]">Actions</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {isLoading ? (
            <tr>
              <td colSpan="12" className="p-6 text-center text-gray-500">
                Loading...
              </td>
            </tr>
          ) : paginatedClients.length === 0 ? (
            <tr>
              <td colSpan="12" className="p-6 text-center text-gray-500">
                No clients found.
              </td>
            </tr>
          ) : (
            paginatedClients.map((client) => (
              <tr key={client.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 w-12 text-center">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(client.id)}
                    onChange={() => toggleSelection(client.id)}
                    className="w-4 h-4"
                  />
                </td>
                <td className="px-6 py-4">{client.id}</td>
                <td className="px-6 py-4">{client.name}</td>
                <td className="px-6 py-4">{client.messenger_id}</td>
                <td className="px-6 py-4">{client.group_name || "G1"}</td>
                <td className="px-6 py-4">{client.connection_name || "—"}</td>
                <td className="px-6 py-4">{renderStatus(client.state)}</td>
                <td className="px-6 py-4">
                  {renderBillingStatus(client.status)}
                </td>
                <td className="px-6 py-4">
                  {client.speed_limit || "unlimited"}
                </td>
                <td className="px-6 py-4">{formatDate(client.billing_date)}</td>
                <td className="px-6 py-4">
                  {client.amt_monthly != null && !isNaN(client.amt_monthly)
                    ? `₱${Number(client.amt_monthly).toFixed(2)}`
                    : "₱0.00"}
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap sm:flex-nowrap gap-2 whitespace-nowrap">
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
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default ClientTable;
