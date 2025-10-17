import React from "react";

const MobileSelectionBar = ({
  paginatedClients,
  selectedIds,
  allSelected,
  filteredClients,
  clients,
  handleSelectAllPage,
  handleSelectAllAcrossPages,
  handleSelectAll,
  clearAllSelection,
}) => {
  const allPageSelected =
    paginatedClients.every((c) => selectedIds.includes(c.id)) &&
    paginatedClients.length > 0;
  const count = selectedIds.length;

  return (
    <div className="sm:hidden mb-3 sticky top-[70px] z-30">
      <div className="flex items-center justify-between bg-white px-3 py-2 rounded-lg shadow-sm border border-gray-200">
        {/* ✅ Select all on current page */}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={allPageSelected}
            onChange={(e) =>
              handleSelectAllPage(e.target.checked, paginatedClients)
            }
            className="w-4 h-4 accent-blue-600"
          />
          <span className="text-sm text-gray-800 font-medium">
            {count > 0
              ? `Selected ${count} client${count > 1 ? "s" : ""}`
              : "Select all on this page"}
          </span>
        </label>

        <div className="flex gap-2">
          {/* ✅ Select all (across pages) */}
          {count > 0 && !allSelected && (
            <button
              onClick={handleSelectAll}
              className="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-md hover:bg-indigo-200 transition"
            >
              All ({clients.length})
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
    </div>
  );
};

export default MobileSelectionBar;
