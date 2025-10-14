// src/features/clients/services/ClientSelection.js
export default class ClientSelection {
  constructor(setSelectedIds) {
    this.setSelectedIds = setSelectedIds;
    this.selected = new Set();
  }

  toggleSelection(id) {
    if (this.selected.has(id)) this.selected.delete(id);
    else this.selected.add(id);
    this.setSelectedIds([...this.selected]);
  }

  toggleSelectAll(clients) {
    if (this.selected.size === clients.length) this.selected.clear();
    else clients.forEach((c) => this.selected.add(c.id));
    this.setSelectedIds([...this.selected]);
  }

  clear() {
    this.selected.clear();
    this.setSelectedIds([]);
  }

  isSelected(id) {
    return this.selected.has(id);
  }
}
