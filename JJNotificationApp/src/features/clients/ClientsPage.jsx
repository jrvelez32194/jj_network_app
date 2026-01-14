import { useState, useMemo, useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import Pagination from "../../components/Pagination";

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
} from "../api/clientsApi";

import { useSendToClientsMutation } from "../messages/messagesApi";

import AddClientDrawer from "./AddClientDrawer";
import ConfirmDialog from "../../components/ConfirmDialog";
import SendDialog from "../../components/SendDialog";
import { InfoDialog } from "../../components/InfoDialog";

import { useWebSocketManager } from "../../hooks/useWebSocketManager";

import StatusFilterGroup from "./components/StatusFilterGroup";
import SearchBar from "./components/SearchBar";
import SelectionControlsForDesktop from "./components/SelectionControlsForDesktop";
import MobileSelectionBar from "./components/MobileSelectionBar";
import ClientToolbar from "./components/ClientToolbar";
import ClientTable from "./components/ClientTable";
import FloatingActionMenu from "./components/FloatingActionMenu";
import MobileClientCards from "./components/MobileClientCards";

const ClientsPage = () => {
  // ----------------------------------------------------------
  // 🧩 Local State
  // ----------------------------------------------------------
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmMessage, setConfirmMessage] = useState("");

  const [sendOpen, setSendOpen] = useState(false);
  const [sendClientIds, setSendClientIds] = useState([]);

  const [fabOpen, setFabOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilters, setStatusFilters] = useState({
    UP: false,
    DOWN: false,
    UNKNOWN: false,
    UNPAID: false,
    LIMITED: false,
    CUTOFF: false,
  });

  const [selectedIds, setSelectedIds] = useState([]);
  const [allSelected, setAllSelected] = useState(false);

  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // ----------------------------------------------------------
  // ⚙️ RTK Query Hooks
  // ----------------------------------------------------------
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

  // ----------------------------------------------------------
  // 🧠 Utilities
  // ----------------------------------------------------------
  const { showToast, Toast } = InfoDialog();
  const dispatch = useDispatch();
  useWebSocketManager({ showToast, dispatch, refetch });

  // ----------------------------------------------------------
  // 📊 Derived Data
  // ----------------------------------------------------------
  const upCount = clients.filter((c) => c.state === "UP").length;
  const downCount = clients.filter((c) => c.state === "DOWN").length;
  const unknownCombinedCount = clients.filter((c) => {
    const isStateUnknown = !["UP", "DOWN"].includes(c.state);
    const isBillingUnknown = !c.billing_date;
    return isStateUnknown || isBillingUnknown;
  }).length;
  const unpaidCount = clients.filter((c) => c.status === "UNPAID").length;
  const limitedCount = clients.filter((c) => c.status === "LIMITED").length;
  const cutoffCount = clients.filter((c) => c.status === "CUTOFF").length;

  // ----------------------------------------------------------
  // 🔍 Filtering & Search
  // ----------------------------------------------------------
  const toggleFilter = (key) => {
    setStatusFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSearch = (value) => setSearchTerm(value);

  const filteredClients = useMemo(() => {
    let result = clients;

    if (searchTerm) {
      const terms = searchTerm
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);

      const groupTerms = terms.filter((term) =>
        clients.some((c) => c.group_name?.toLowerCase() === term)
      );
      const otherTerms = terms.filter((term) => !groupTerms.includes(term));

      result = result.filter((c) => {
        const billingDate = c.billing_date
          ? new Date(c.billing_date).toISOString().split("T")[0]
          : "";
        const id = c.id?.toString() || "";
        const name = c.name || "";
        const messenger_id = c.messenger_id || "";
        const group_name = c.group_name || "";
        const connection_name = c.connection_name || "";
        const state = c.state || "";
        const status = c.status || "";

        if (groupTerms.length > 0) {
          if (!groupTerms.includes(group_name.toLowerCase())) return false;
          if (!otherTerms.length) return true;

          return otherTerms.some((term) =>
            [
              id,
              name,
              messenger_id,
              connection_name,
              state,
              status,
              billingDate,
            ].some((v) => v.toLowerCase().includes(term))
          );
        }

        return terms.some((term) =>
          [
            id,
            name,
            messenger_id,
            group_name,
            connection_name,
            state,
            status,
            billingDate,
          ].some((v) => v.toLowerCase().includes(term))
        );
      });
    }

    const activeFilters = Object.entries(statusFilters)
      .filter(([_, v]) => v)
      .map(([k]) => k);

    if (activeFilters.length) {
      result = result.filter((c) => {
        const matchState = activeFilters.includes(c.state);
        const matchStatus = activeFilters.includes(c.status);
        const isUnknown =
          activeFilters.includes("UNKNOWN") &&
          (!["UP", "DOWN"].includes(c.state) || !c.billing_date);
        return matchState || matchStatus || isUnknown;
      });
    }

    return result;
  }, [clients, searchTerm, statusFilters]);

  // ----------------------------------------------------------
  // 📄 Pagination
  // ----------------------------------------------------------
  const totalPages = Math.ceil(filteredClients.length / pageSize);
  const prevSearchRef = useRef("");
  const prevFiltersRef = useRef(statusFilters);

  useEffect(() => {
    const filtersChanged =
      JSON.stringify(prevFiltersRef.current) !== JSON.stringify(statusFilters);

    if (searchTerm !== prevSearchRef.current || filtersChanged) {
      setCurrentPage(1);
      prevSearchRef.current = searchTerm;
      prevFiltersRef.current = statusFilters;
    }
  }, [searchTerm, statusFilters]);

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages || 1);
  }, [totalPages, currentPage]);

  const paginatedClients = filteredClients
    .map((c) => ({ ...c, status: !c.billing_date ? "UNKNOWN" : c.status }))
    .slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // ----------------------------------------------------------
  // ✅ Selection Handlers
  // ----------------------------------------------------------
  const toggleSelection = (id) => {
    setSelectedIds((prev) => {
      const newSelected = prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id];

      if (allSelected && !newSelected.includes(id)) setAllSelected(false);

      return newSelected;
    });
  };

  const handleSelectAllPage = (checked, pageClients) => {
    const pageIds = pageClients.map((c) => c.id);
    setSelectedIds((prev) =>
      checked
        ? [...new Set([...prev, ...pageIds])]
        : prev.filter((id) => !pageIds.includes(id))
    );
  };

  const handleSelectAllAcrossPages = () => {
    setSelectedIds(filteredClients.map((c) => c.id));
    setAllSelected(true);
  };

  const handleSelectAll = () => {
    setSelectedIds(clients.map((c) => c.id));
    setAllSelected(true);
  };

  const clearAllSelection = () => {
    setSelectedIds([]);
    setAllSelected(false);
  };

  // ----------------------------------------------------------
  // 💾 CRUD Operations
  // ----------------------------------------------------------
  const handleSaveClient = async (clientData) => {
    try {
      clientData.group_name ||= "G1";
      clientData.connection_name ||= null;

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

  const handleBulkDelete = () => {
    if (!selectedIds.length) return;
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

  // ----------------------------------------------------------
  // 💰 Billing Actions
  // ----------------------------------------------------------
  const handleSetPaid = async (id) => {
    try {
      await setPaid([id]).unwrap();
      showToast("Client marked as PAID ✅");
    } catch {
      showToast("Failed to set paid ❌", "error");
    }
  };

  const handleBulkSetPaid = async () => {
    if (!selectedIds.length) return;
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
      await setUnpaid([id]).unwrap();
      showToast("Client marked as UNPAID ❌");
    } catch {
      showToast("Failed to set unpaid ❌", "error");
    }
  };

  const handleBulkSetUnpaid = async () => {
    if (!selectedIds.length) return;
    try {
      await setUnpaidBulk(selectedIds).unwrap();
      showToast(`❌ Set ${selectedIds.length} clients to UNPAID`);
      clearAllSelection();
    } catch {
      showToast("❌ Failed to update billing status", "error");
    }
  };

  // ----------------------------------------------------------
  // ✉️ Messaging
  // ----------------------------------------------------------
  const handleOpenSend = () => {
    if (!selectedIds.length) return;
    setSendClientIds(selectedIds);
    setSendOpen(true);
  };

  const handleSend = async ({ title, message }) => {
    if (!title || !message)
      return showToast("Title and message are required", "error");

    try {
      const numericIds = sendClientIds.map(Number);

      await sendToClients({ title, message, client_ids: numericIds }).unwrap();

      showToast("Messages sent successfully ✅");
      setSendOpen(false);
      setSendClientIds([]);
    } catch (err) {
      console.error("Send error:", err);
      showToast("Failed to send messages ❌", "error");
    }
  };

  // ----------------------------------------------------------
  // 🔄 Sync
  // ----------------------------------------------------------
  const handleSyncClients = async () => {
    try {
      await syncClients().unwrap();
      showToast("✅ Clients synced successfully");
    } catch {
      showToast("❌ Failed to sync clients", "error");
    }
  };

  // ----------------------------------------------------------
  // 📆 Helpers
  // ----------------------------------------------------------
  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    const d = new Date(dateString);
    return isNaN(d.getTime()) ? "N/A" : d.toISOString().split("T")[0];
  };

  const renderStatus = (state) => {
    const map = {
      UP: ["green-500", "green-100", "green-700"],
      DOWN: ["red-500", "red-100", "red-700"],
      UNKNOWN: ["gray-400", "gray-100", "gray-700"],
    };
    const [dot, bg, text] = map[state] || map.UNKNOWN;

    return (
      <div className="flex items-center gap-1">
        <span
          className={`w-2.5 h-2.5 rounded-full bg-${dot} animate-pulse`}
        ></span>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-semibold bg-${bg} text-${text}`}
        >
          {state}
        </span>
      </div>
    );
  };

  const renderBillingStatus = (status) => {
    const base =
      "px-2 py-1 text-xs font-semibold rounded-full flex items-center gap-1 w-fit";
    const map = {
      PAID: ["green-500", "green-100", "green-700"],
      UNPAID: ["yellow-400", "yellow-100", "yellow-700"],
      LIMITED: ["orange-400", "orange-100", "orange-700"],
      CUTOFF: ["red-600", "red-200", "red-800"],
      UNKNOWN: ["gray-400", "gray-100", "gray-700"],
    };
    const [dot, bg, text] = map[status] || map.UNKNOWN;

    return (
      <span className={`${base} bg-${bg} text-${text}`}>
        <span className={`w-2 h-2 bg-${dot} rounded-full`}></span>
        {status}
      </span>
    );
  };

  // ----------------------------------------------------------
  // 🖼️ Render
  // ----------------------------------------------------------
  return (
    <div className="p-4 max-w-6xl mx-auto pb-28">
      <StatusFilterGroup
        statusFilters={statusFilters}
        toggleFilter={toggleFilter}
        upCount={upCount}
        downCount={downCount}
        unknownCombinedCount={unknownCombinedCount}
        unpaidCount={unpaidCount}
        limitedCount={limitedCount}
        cutoffCount={cutoffCount}
      />

      <SearchBar value={searchTerm} onSearch={handleSearch} />

      <SelectionControlsForDesktop
        selectedIds={selectedIds}
        paginatedClients={paginatedClients}
        filteredClients={filteredClients}
        clients={clients}
        allSelected={allSelected}
        handleSelectAllPage={handleSelectAllPage}
        handleSelectAllAcrossPages={handleSelectAllAcrossPages}
        handleSelectAll={handleSelectAll}
        clearAllSelection={clearAllSelection}
      />

      <MobileSelectionBar
        paginatedClients={paginatedClients}
        selectedIds={selectedIds}
        allSelected={allSelected}
        filteredClients={filteredClients}
        clients={clients}
        handleSelectAllPage={handleSelectAllPage}
        handleSelectAllAcrossPages={handleSelectAllAcrossPages}
        handleSelectAll={handleSelectAll}
        clearAllSelection={clearAllSelection}
      />

      <ClientToolbar
        selectedIds={selectedIds}
        handleBulkDelete={handleBulkDelete}
        handleBulkSetPaid={handleBulkSetPaid}
        handleBulkSetUnpaid={handleBulkSetUnpaid}
        handleOpenSend={handleOpenSend}
        handleSyncClients={handleSyncClients}
        isSyncing={isSyncing}
        setEditingClient={setEditingClient}
        setIsDrawerOpen={setIsDrawerOpen}
      />

      <ClientTable
        paginatedClients={paginatedClients}
        selectedIds={selectedIds}
        isLoading={isLoading}
        handleSelectAllPage={handleSelectAllPage}
        toggleSelection={toggleSelection}
        handleDeleteClient={handleDeleteClient}
        handleSetPaid={handleSetPaid}
        handleSetUnpaid={handleSetUnpaid}
        renderStatus={renderStatus}
        renderBillingStatus={renderBillingStatus}
        formatDate={formatDate}
        setEditingClient={setEditingClient}
        setIsDrawerOpen={setIsDrawerOpen}
      />

      <FloatingActionMenu
        fabOpen={fabOpen}
        setFabOpen={setFabOpen}
        selectedIds={selectedIds}
        handleBulkDelete={handleBulkDelete}
        handleBulkSetPaid={handleBulkSetPaid}
        handleBulkSetUnpaid={handleBulkSetUnpaid}
        handleOpenSend={handleOpenSend}
        handleSyncClients={handleSyncClients}
        setEditingClient={setEditingClient}
        setIsDrawerOpen={setIsDrawerOpen}
      />

      <MobileClientCards
        paginatedClients={paginatedClients}
        selectedIds={selectedIds}
        toggleSelection={toggleSelection}
        renderStatus={renderStatus}
        renderBillingStatus={renderBillingStatus}
        formatDate={formatDate}
        handleDeleteClient={handleDeleteClient}
        handleSetPaid={handleSetPaid}
        handleSetUnpaid={handleSetUnpaid}
        setEditingClient={setEditingClient}
        setIsDrawerOpen={setIsDrawerOpen}
      />

      <Pagination
        totalItems={filteredClients.length}
        pageSize={pageSize}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />

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
        selectedClientIds={sendClientIds} // ✅ FIX
      />

      <Toast />
    </div>
  );
};

export default ClientsPage;
