import React from "react";

const SelectionControlsForDesktop = ({
  selectedIds,
  paginatedClients,
  filteredClients,
  clients,
  allSelected,
  handleSelectAllPage,
  handleSelectAllAcrossPages,
  handleSelectAll,
  clearAllSelection,
}) => {
  // ✅ If nothing selected, hide component
  if (selectedIds.length === 0) return null;

  return (
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
        {/* {!allSelected && (
          <button
            onClick={handleSelectAllAcrossPages}
            className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm"
          >
            Select Across Pages ({filteredClients.length})
          </button>
        )} */}

        {/* ✅ Select all clients */}
        {!allSelected && (
          <button
            onClick={handleSelectAll}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-sm"
          >
            Select All ({clients.length})
          </button>
        )}

        {/* ✅ Deselect all */}
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
  );
};

export default SelectionControlsForDesktop;
