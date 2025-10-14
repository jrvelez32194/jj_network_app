import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function Pagination({
  totalItems,
  pageSize,
  currentPage,
  setCurrentPage,
}) {
  if (totalItems === 0) return null;

  const totalPages = Math.ceil(totalItems / pageSize);
  if (totalPages <= 1) return null;

  const handlePageChange = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
  };

  const getPageNumbers = () => {
    const isMobile = window.innerWidth < 640;
    const maxButtons = isMobile ? 3 : 7;
    const half = Math.floor(maxButtons / 2);

    let start = Math.max(1, currentPage - half);
    let end = Math.min(totalPages, currentPage + half);

    if (end - start + 1 < maxButtons) {
      if (start === 1) end = Math.min(totalPages, start + maxButtons - 1);
      else if (end === totalPages) start = Math.max(1, end - maxButtons + 1);
    }

    const range = [];
    if (start > 1) {
      range.push(1);
      if (start > 2) range.push("...");
    }

    for (let i = start; i <= end; i++) range.push(i);

    if (end < totalPages) {
      if (end < totalPages - 1) range.push("...");
      range.push(totalPages);
    }

    return range;
  };

  const pageNumbers = getPageNumbers();

  return (
    <div className="flex justify-between items-center mt-6 flex-wrap gap-3 text-sm text-gray-700">
      {/* Left side: Page info */}
      <div className="text-gray-600">
        Showing{" "}
        <span className="font-semibold">
          {(currentPage - 1) * pageSize + 1}
        </span>{" "}
        to{" "}
        <span className="font-semibold">
          {Math.min(currentPage * pageSize, totalItems)}
        </span>{" "}
        of <span className="font-semibold">{totalItems}</span> entries
      </div>

      {/* Right side: Buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => handlePageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-100 disabled:opacity-50 transition-all"
        >
          <ChevronLeft size={16} />
          <span className="hidden sm:inline">Prev</span>
        </button>

        {pageNumbers.map((page, i) =>
          page === "..." ? (
            <span key={i} className="px-3 py-1.5 text-gray-400 select-none">
              ...
            </span>
          ) : (
            <button
              key={i}
              onClick={() => handlePageChange(page)}
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                currentPage === page
                  ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                  : "border-gray-300 hover:bg-gray-100"
              }`}
            >
              {page}
            </button>
          )
        )}

        <button
          onClick={() => handlePageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-100 disabled:opacity-50 transition-all"
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
