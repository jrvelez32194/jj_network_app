import { useState, useMemo, useEffect } from "react";
import { useDispatch } from "react-redux";
import { MoreVertical } from "lucide-react";
import Pagination from "../../components/common/Pagination";
import {
  useGetClientsQuery,
  useAddClientMutation,
  useUpdateClientMutation,
  useDeleteClientMutation,
  useDeleteClientsMutation,
  useSyncClientsMutation,
  useSetPaidBulkMutation,
  useSetPaidMutation,
  useSetUnpaidBulkMutation,
  useSetUnpaidMutation,
} from "../clients/clientsApi";
import { useSendToClientsMutation } from "../messages/messagesApi";
import AddClientDrawer from "./AddClientDrawer";
import ConfirmDialog from "../../components/ConfirmDialog";
import SendDialog from "../../components/SendDialog";
import { InfoDialog } from "../../components/InfoDialog";
import { useWebSocketManager } from "../../hooks/useWebSocketManager";

const ClientsPage = () => {
  // ✅ State
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmMessage, setConfirmMessage] = useState("");

  const [sendOpen, setSendOpen] = useState(false);
  const [sendClientIds, setSendClientIds] = useState([]);

  const { data: clients = [], isLoading, refetch } = useGetClientsQuery();
  const [addClient] = useAddClientMutation();
  const [updateClient] = useUpdateClientMutation();
  const [deleteClient] = useDeleteClientMutation();
  const [deleteClients] = useDeleteClientsMutation();
  const [sendToClients] = useSendToClientsMutation();
  const [syncClients, { isLoading: isSyncing }] = useSyncClientsMutation();
  const [setPaidBulk] = useSetPaidBulkMutation();
  const [setPaid] = useSetPaidMutation();
  const [setUnpaidBulk] = useSetUnpaidBulkMutation();
  const [setUnpaid] = useSetUnpaidMutation();
  const { showToast, Toast } = InfoDialog();
  const [fabOpen, setFabOpen] = useState(false);

  // ✅ Count client states and statuses
  const upCount = clients.filter((c) => c.state === "UP").length;
  const downCount = clients.filter((c) => c.state === "DOWN").length;
  const unknownCombinedCount = clients.filter((c) => {
    const isStateUnknown = !["UP", "DOWN"].includes(c.state);
    const isBillingUnknown = !c.billing_date;
    // Match the same logic as your UNKNOWN filter
    return isStateUnknown || isBillingUnknown;
  }).length;

  const [statusFilters, setStatusFilters] = useState({
    UP: false,
    DOWN: false,
    UNKNOWN: false,
    UNPAID: false,
    LIMITED: false,
    CUTOFF: false,
  });

  const unpaidCount = clients.filter((c) => c.status === "UNPAID").length;
  const limitedCount = clients.filter((c) => c.status === "LIMITED").length;
  const cutoffCount = clients.filter((c) => c.status === "CUTOFF").length;

  const dispatch = useDispatch();

  useWebSocketManager({ showToast, dispatch, refetch });

  const handleSetPaid = async (id) => {
    try {
      await setPaid([id]).unwrap(); // send single id as array
      showToast("Client marked as PAID ✅");
    } catch {
      showToast("Failed to set paid ❌", "error");
    }
  };

  // ✅ Bulk Set Paid
  const handleBulkSetPaid = async () => {
    if (selectedIds.length === 0) return;
    try {
      await setPaidBulk(selectedIds).unwrap();
      showToast(`✅ Set ${selectedIds.length} clients to PAID`);
      clearAllSelection();
    } catch {
      showToast("❌ Failed to update billing status", "error");
    }
  };

  const handleSetUnpaid = async (id) => {
    try {
      await setUnpaid([id]).unwrap(); // single id as array
      showToast("Client marked as UNPAID ❌");
    } catch {
      showToast("Failed to set unpaid ❌", "error");
    }
  };

  const handleBulkSetUnpaid = async () => {
    if (selectedIds.length === 0) return;
    try {
      await setUnpaidBulk(selectedIds).unwrap();
      showToast(`❌ Set ${selectedIds.length} clients to UNPAID`);
      clearAllSelection();
    } catch {
      showToast("❌ Failed to update billing status", "error");
    }
  };

  // ✅ Status filters (checkboxes)
  const toggleFilter = (key) => {
    setStatusFilters((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  // ✅ Search
  const [searchTerm, setSearchTerm] = useState("");
  const filteredClients = useMemo(() => {
    let result = clients;

    // 🔍 Search filter
    if (searchTerm) {
      const terms = searchTerm
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter((t) => t.length > 0);

      result = result.filter((c) => {
        const id = c.id?.toString().toLowerCase() || "";
        const name = c.name?.toLowerCase() || "";
        const messenger_id = c.messenger_id?.toLowerCase() || "";
        const group_name = c.group_name?.toLowerCase() || "";
        const connection_name = c.connection_name?.toLowerCase() || "";
        const state = c.state?.toLowerCase() || "";
        const status = c.status?.toLowerCase() || "";

        return terms.some((term) => {
          // ✅ Exact match for group_name only
          const isExactGroupMatch = group_name === term;

          // ✅ Partial match for all others
          const isLikeMatch =
            id.includes(term) ||
            name.includes(term) ||
            messenger_id.includes(term) ||
            connection_name.includes(term) ||
            state.includes(term) ||
            status.includes(term);

          return isExactGroupMatch || isLikeMatch;
        });
      });
    }

    const activeFilters = Object.entries(statusFilters)
      .filter(([_, v]) => v)
      .map(([k]) => k);

    if (activeFilters.length > 0) {
      result = result.filter((c) => {
        const matchState = activeFilters.includes(c.state);
        const matchStatus = activeFilters.includes(c.status);

        // 🕵️‍♂️ Handle UNKNOWN filter properly:
        // Include clients with missing billing_date or undefined state
        const isUnknown =
          activeFilters.includes("UNKNOWN") &&
          (!["UP", "DOWN"].includes(c.state) || !c.billing_date);

        return matchState || matchStatus || isUnknown;
      });
    }

    return result;
  }, [clients, searchTerm, statusFilters]);

  // ✅ Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // ✅ Reset only on search
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm]);

  // ✅ Safe pagination
  const totalPages = Math.ceil(filteredClients.length / pageSize);
  const currentPageSafe = Math.min(currentPage, totalPages || 1);
  const paginatedClients = filteredClients
    .map((c) => ({
      ...c,
      // If there's no billing_date, force status to UNKNOWN
      status: !c.billing_date ? "UNKNOWN" : c.status,
    }))
    .slice((currentPageSafe - 1) * pageSize, currentPageSafe * pageSize);

  useEffect(() => {
    const savedPage = Number(localStorage.getItem("clientsPage")) || 1;
    setCurrentPage(savedPage);
  }, []);

  useEffect(() => {
    localStorage.setItem("clientsPage", currentPage);
  }, [currentPage]);

  const handleSearch = (value) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  // ✅ Selection
  const [selectedIds, setSelectedIds] = useState([]);
  const [allSelected, setAllSelected] = useState(false);

  // Toggle individual selection
  const toggleSelection = (id) => {
    setSelectedIds((prev) => {
      const newSelected = prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id];

      // if user unchecks any id, remove global select-all
      if (allSelected && !newSelected.includes(id)) {
        setAllSelected(false);
      }

      return newSelected;
    });
  };

  // ✅ Select all on current page
  const handleSelectAllPage = (checked, pageClients) => {
    if (checked) {
      const pageIds = pageClients.map((c) => c.id);
      setSelectedIds((prev) => [...new Set([...prev, ...pageIds])]);
    } else {
      const pageIds = pageClients.map((c) => c.id);
      setSelectedIds((prev) => prev.filter((id) => !pageIds.includes(id)));
    }
  };

  // ✅ Select all across filtered results (not all records)
  const handleSelectAllAcrossPages = () => {
    const allFilteredIds = filteredClients.map((c) => c.id);
    setSelectedIds(allFilteredIds);
    setAllSelected(true);
  };

  // ✅ Optional: Select absolutely all clients
  const handleSelectAll = () => {
    const allIds = clients.map((c) => c.id);
    setSelectedIds(allIds);
    setAllSelected(true);
  };

  // ✅ Deselect everything
  const clearAllSelection = () => {
    setSelectedIds([]);
    setAllSelected(false);
  };

  // ✅ Save client
  const handleSaveClient = async (clientData) => {
    try {
      if (!clientData.group_name) {
        clientData.group_name = "G1";
      }
      if (!clientData.connection_name) {
        clientData.connection_name = null;
      }

      if (editingClient) {
        await updateClient({ id: editingClient.id, ...clientData }).unwrap();
        showToast("Client updated ✅");
      } else {
        await addClient(clientData).unwrap();
        showToast("Client added ✅");
      }
      setIsDrawerOpen(false);
      setEditingClient(null);
    } catch (err) {
      console.error("Save failed:", err);
      showToast(err?.data?.detail || "Something went wrong ❌", "error");
    }
  };

  // ✅ Delete single
  const handleDeleteClient = (id) => {
    setConfirmMessage("Are you sure you want to delete this client?");
    setConfirmAction(() => async () => {
      try {
        await deleteClient(id).unwrap();
        showToast("Client deleted ✅");
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
      `Are you sure you want to delete ${selectedIds.length} clients?`
    );
    setConfirmAction(() => async () => {
      try {
        await deleteClients(selectedIds).unwrap();
        showToast(`Deleted ${selectedIds.length} clients ✅`);
        clearAllSelection();
        return true;
      } catch {
        showToast("Failed to delete ❌", "error");
        return false;
      }
    });
    setConfirmOpen(true);
  };

  // ✅ Send
  const handleOpenSend = () => {
    if (selectedIds.length === 0) return;
    setSendClientIds(selectedIds);
    setSendOpen(true);
  };

  const handleSend = async (templateId) => {
    try {
      const numericIds = sendClientIds.map((id) => Number(id));
      await sendToClients({
        template_id: templateId,
        client_ids: numericIds,
      }).unwrap();

      showToast("Messages sent successfully!");
      setSendOpen(false);
      setSendClientIds([]);
    } catch (error) {
      console.error("Send error:", error);
      showToast("Failed to send messages", "error");
    }
  };

  // ✅ Sync
  const handleSyncClients = async () => {
    try {
      await syncClients().unwrap();
      showToast("✅ Clients synced successfully");
    } catch {
      showToast("❌ Failed to sync clients", "error");
    }
  };

  // ✅ Helper: Format date safely
  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "N/A";
    return d.toISOString().split("T")[0]; // YYYY-MM-DD
  };

  // ✅ Status Badge Renderer
  const renderStatus = (state) => {
    if (state === "UP") {
      return (
        <div className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
            UP
          </span>
        </div>
      );
    }
    if (state === "DOWN") {
      return (
        <div className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
            DOWN
          </span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1">
        <span className="w-2.5 h-2.5 rounded-full bg-gray-400"></span>
        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">
          UNKNOWN
        </span>
      </div>
    );
  };

  // 🎨 Render billing status badges (PAID, UNPAID, LIMITED, CUTOFF)
  const renderBillingStatus = (status) => {
    const base =
      "px-2 py-1 text-xs font-semibold rounded-full flex items-center gap-1 w-fit";

    switch (status) {
      case "PAID":
        return (
          <span className={`${base} bg-green-100 text-green-700`}>
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            PAID
          </span>
        );
      case "UNPAID":
        return (
          <span className={`${base} bg-yellow-100 text-yellow-700`}>
            <span className="w-2 h-2 bg-yellow-400 rounded-full"></span>
            UNPAID
          </span>
        );
      case "LIMITED":
        return (
          <span className={`${base} bg-orange-100 text-orange-700`}>
            <span className="w-2 h-2 bg-orange-400 rounded-full"></span>
            LIMITED
          </span>
        );
      case "CUTOFF":
        return (
          <span className={`${base} bg-red-200 text-red-800`}>
            <span className="w-2 h-2 bg-red-600 rounded-full"></span>
            CUTOFF
          </span>
        );
      default:
        return (
          <span className={`${base} bg-gray-100 text-gray-700`}>
            <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
            UNKNOWN
          </span>
        );
    }
  };

  return (
    <div className="p-4 max-w-6xl mx-auto pb-28">
      {/* ✅ Dashboard Summary (with UNPAID, LIMITED, CUTOFF) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-wrap gap-2 mb-4">
        {[
          { key: "UP", color: "green", label: `UP: ${upCount}` },
          { key: "DOWN", color: "red", label: `DOWN: ${downCount}` },
          {
            key: "UNKNOWN",
            color: "gray",
            label: `UNKNOWN: ${unknownCombinedCount}`,
          },
          { key: "UNPAID", color: "yellow", label: `UNPAID: ${unpaidCount}` },
          {
            key: "LIMITED",
            color: "orange",
            label: `LIMITED: ${limitedCount}`,
          },
          { key: "CUTOFF", color: "red", label: `CUTOFF: ${cutoffCount}` },
        ].map(({ key, color, label }) => (
          <label
            key={key}
            className={`flex items-center justify-between gap-2 rounded-md py-1 px-3 border cursor-pointer transition ${
              statusFilters[key]
                ? `bg-${color}-200 border-${color}-500`
                : `bg-${color}-100 border-transparent`
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`w-3 h-3 bg-${color}-500 rounded-full`}></span>
              <span className="font-semibold text-sm text-gray-800">
                {label}
              </span>
            </div>
            <input
              type="checkbox"
              checked={statusFilters[key]}
              onChange={() => toggleFilter(key)}
              className="w-4 h-4 accent-current"
            />
          </label>
        ))}
      </div>

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
            placeholder="Search clients..."
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

      {/* ✅ Selection controls remain for Desktop */}
      {selectedIds.length > 0 && (
        <div className="hidden sm:flex flex-wrap justify-between items-center gap-2 mb-6 px-2">
          <div className="text-sm text-gray-700">
            Selected {selectedIds.length} client
            {selectedIds.length > 1 ? "s" : ""}
          </div>

          <div className="flex gap-2">
            {/* ✅ Select all on current page */}
            <button
              onClick={() => handleSelectAllPage(true, paginatedClients)}
              className="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded text-sm"
            >
              Select All (Page)
            </button>

            {/* ✅ Select across all filtered pages */}
            {!allSelected && (
              <button
                onClick={handleSelectAllAcrossPages}
                className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm"
              >
                Select Across Pages ({filteredClients.length})
              </button>
            )}

            {/* ✅ Optional: Select absolutely all clients */}
            {!allSelected && (
              <button
                onClick={handleSelectAll}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-sm"
              >
                Select All ({clients.length})
              </button>
            )}

            {/* ✅ Deselect everything */}
            {allSelected && (
              <button
                onClick={clearAllSelection}
                className="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded text-sm"
              >
                Clear All
              </button>
            )}
          </div>
        </div>
      )}

      {/* ✅ Mobile Selection Controls */}
      <div className="sm:hidden mb-3">
        <div className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-lg shadow-sm border border-gray-200">
          {/* ✅ Select all on current page */}
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={
                paginatedClients.every((c) => selectedIds.includes(c.id)) &&
                paginatedClients.length > 0
              }
              onChange={(e) =>
                handleSelectAllPage(e.target.checked, paginatedClients)
              }
              className="w-4 h-4 accent-blue-600"
            />
            <span className="text-sm text-gray-700 font-medium">
              Select all on this page
            </span>
          </label>

          {/* ✅ When some are selected, offer “Select Across Pages” */}
          {selectedIds.length > 0 && !allSelected && (
            <button
              onClick={handleSelectAllAcrossPages}
              className="text-xs bg-blue-100 text-blue-700 px-2.5 py-1 rounded-md hover:bg-blue-200 transition"
            >
              Select Across Pages ({filteredClients.length})
            </button>
          )}

          {/* ✅ Optional — Select ALL records (no filter) */}
          {selectedIds.length > 0 && !allSelected && (
            <button
              onClick={handleSelectAll}
              className="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-md hover:bg-indigo-200 transition"
            >
              Select All ({clients.length})
            </button>
          )}

          {/* ✅ Deselect all */}
          {allSelected && (
            <button
              onClick={clearAllSelection}
              className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-md hover:bg-gray-200 transition"
            >
              Clear
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
          <button
            onClick={handleBulkSetPaid} // ✅ new
            disabled={selectedIds.length === 0}
            className={`px-4 py-2 rounded ${
              selectedIds.length === 0
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-yellow-600 text-white hover:bg-yellow-700"
            }`}
          >
            💰 Set Paid {selectedIds.length > 0 && `(${selectedIds.length})`}
          </button>

          <button
            onClick={handleBulkSetUnpaid}
            disabled={selectedIds.length === 0}
            className={`px-4 py-2 rounded ${
              selectedIds.length === 0
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-orange-600 text-white hover:bg-orange-700"
            }`}
          >
            ❌ Set Unpaid {selectedIds.length > 0 && `(${selectedIds.length})`}
          </button>

          <button
            onClick={handleOpenSend}
            disabled={selectedIds.length === 0}
            className={`px-4 py-2 rounded ${
              selectedIds.length === 0
                ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
          >
            📤 Send {selectedIds.length > 0 && `(${selectedIds.length})`}
          </button>
          <button
            onClick={handleSyncClients}
            disabled={isSyncing}
            className="px-4 py-2 rounded bg-purple-600 text-white hover:bg-purple-700"
          >
            {isSyncing ? "⏳ Syncing..." : "🔄 Sync Clients"}
          </button>
        </div>
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

      {/* ✅ Desktop Table */}
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
                <td colSpan="11" className="p-6 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            ) : paginatedClients.length === 0 ? (
              <tr>
                <td colSpan="11" className="p-6 text-center text-gray-500">
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
                  <td className="px-6 py-4">
                    {formatDate(client.billing_date)}
                  </td>
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

      {/* ✅ Floating Action Button Menu (Mobile Only) */}
      <div className="sm:hidden fixed bottom-6 right-6 flex flex-col items-end space-y-2 z-50">
        {fabOpen && (
          <div className="flex flex-col items-end space-y-2 mb-2 transition-all duration-300">
            {/* Delete */}
            <button
              onClick={() => {
                handleBulkDelete();
                setFabOpen(false);
              }}
              disabled={selectedIds.length === 0}
              className={`p-3 rounded-full shadow-lg text-white ${
                selectedIds.length === 0
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
              disabled={selectedIds.length === 0}
              className={`p-3 rounded-full shadow-lg text-white ${
                selectedIds.length === 0
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
              disabled={selectedIds.length === 0}
              className={`p-3 rounded-full shadow-lg text-white ${
                selectedIds.length === 0
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-orange-600 hover:bg-orange-700"
              }`}
            >
              ❌ Set Unpaid
            </button>

            {/* Send */}
            <button
              onClick={() => {
                handleOpenSend();
                setFabOpen(false);
              }}
              disabled={selectedIds.length === 0}
              className={`p-3 rounded-full shadow-lg text-white ${
                selectedIds.length === 0
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
              🔄 Sync from Messeger
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

        {/* ✅ Modern Menu FAB Toggle */}
        <button
          onClick={() => setFabOpen(!fabOpen)}
          className="p-4 rounded-full bg-purple-600 text-white shadow-xl hover:bg-purple-700 transition-transform transform hover:scale-105"
        >
          <MoreVertical className="w-6 h-6" />
        </button>
      </div>

      {/* ✅ Mobile Card View */}
      <div className="sm:hidden flex flex-col gap-4">
        {paginatedClients.map((client) => (
          <div
            key={client.id}
            className="bg-white p-4 rounded-lg shadow border"
          >
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

      {/* ✅ Global Pagination */}
      <Pagination
        totalItems={filteredClients.length}
        pageSize={pageSize}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />

      {/* ✅ Modals */}
      <AddClientDrawer
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setEditingClient(null);
        }}
        onSave={handleSaveClient}
        editingClient={editingClient}
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

      <SendDialog
        isOpen={sendOpen}
        onClose={() => setSendOpen(false)}
        onSend={handleSend}
      />

      <Toast />
    </div>
  );
};

export default ClientsPage;
