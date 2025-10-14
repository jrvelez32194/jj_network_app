// src/features/clients/services/ClientFilter.js

class ClientFilter {
  static search(clients, term) {
    if (!term) return clients;
    const q = term.toLowerCase();
    return clients.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.mac_address?.toLowerCase().includes(q) ||
        c.ip_address?.toLowerCase().includes(q)
    );
  }

  static filterByStatus(clients, filters) {
    if (!filters.length) return clients;
    return clients.filter((c) => filters.includes(c.status));
  }

  static paginate(clients, currentPage, perPage) {
    const start = (currentPage - 1) * perPage;
    return clients.slice(start, start + perPage);
  }

  static computeCounts(clients) {
    return {
      up: clients.filter((c) => c.state === "UP").length,
      down: clients.filter((c) => c.state === "DOWN").length,
      unknown: clients.filter(
        (c) => !["UP", "DOWN"].includes(c.state) || !c.billing_date
      ).length,
      unpaid: clients.filter((c) => c.status === "UNPAID").length,
      limited: clients.filter((c) => c.status === "LIMITED").length,
      cutoff: clients.filter((c) => c.status === "CUTOFF").length,
    };
  }
}

export default ClientFilter;
