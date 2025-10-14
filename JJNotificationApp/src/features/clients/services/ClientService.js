export default class ClientService {
  constructor({
    addClient,
    updateClient,
    deleteClient,
    deleteClients,
    syncClients,
    showToast,
  }) {
    this.addClient = addClient;
    this.updateClient = updateClient;
    this.deleteClient = deleteClient;
    this.deleteClients = deleteClients;
    this.syncClients = syncClients;
    this.showToast = showToast; // ✅ new
  }

  async handleDeleteClient(id) {
    try {
      await this.deleteClient(id).unwrap();
      this.showToast("Client deleted successfully.", "success");
    } catch {
      this.showToast("Failed to delete client.", "error");
    }
  }

  async handleBulkDelete(selectedIds) {
    if (!selectedIds.length) return;
    try {
      await this.deleteClients(selectedIds).unwrap();
      this.showToast("Selected clients deleted.", "success");
    } catch {
      this.showToast("Bulk delete failed.", "error");
    }
  }

  async handleBulkStatus(selectedIds, status) {
    if (!selectedIds.length) return;
    try {
      const promises = selectedIds.map((id) =>
        this.updateClient({ id, status }).unwrap()
      );
      await Promise.all(promises);
      this.showToast(`Clients updated to ${status}.`, "success");
    } catch {
      this.showToast("Bulk update failed.", "error");
    }
  }

  async handleSyncClients() {
    try {
      await this.syncClients().unwrap();
      this.showToast("Clients synchronized successfully.", "success");
    } catch {
      this.showToast("Client sync failed.", "error");
    }
  }
}
