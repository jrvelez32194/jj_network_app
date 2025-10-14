// StatusFilterGroup.jsx
import React from "react";

const StatusFilterGroup = ({
  statusFilters,
  toggleFilter,
  upCount,
  downCount,
  unknownCombinedCount,
  unpaidCount,
  limitedCount,
  cutoffCount,
}) => {
  const statuses = [
    { key: "UP", color: "green", label: `UP: ${upCount}` },
    { key: "DOWN", color: "red", label: `DOWN: ${downCount}` },
    {
      key: "UNKNOWN",
      color: "gray",
      label: `UNKNOWN: ${unknownCombinedCount}`,
    },
    { key: "UNPAID", color: "yellow", label: `UNPAID: ${unpaidCount}` },
    { key: "LIMITED", color: "orange", label: `LIMITED: ${limitedCount}` },
    { key: "CUTOFF", color: "red", label: `CUTOFF: ${cutoffCount}` },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-wrap gap-2 mb-4">
      {statuses.map(({ key, color, label }) => (
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
            <span className="font-semibold text-sm text-gray-800">{label}</span>
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
  );
};

export default StatusFilterGroup;
