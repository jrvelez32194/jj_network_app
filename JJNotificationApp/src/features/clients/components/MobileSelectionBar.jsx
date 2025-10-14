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

  return (
    <div className="sm:hidden mb-3">
      <div className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-lg shadow-sm border border-gray-200">
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
          <span className="text-sm text-gray-700 font-medium">
            Select all on this page
          </span>
        </label>

        {/* ✅ When some are selected, offer “Select Across Pages” */}
        {/* {selectedIds.length > 0 && !allSelected && (
          <button
            onClick={handleSelectAllAcrossPages}
            className="text-xs bg-blue-100 text-blue-700 px-2.5 py-1 rounded-md hover:bg-blue-200 transition"
          >
            Select Across Pages ({filteredClients.length})
          </button>
        )} */}

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
  );
};

export default MobileSelectionBar;
