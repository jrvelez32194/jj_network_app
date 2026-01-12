import React, { useState, useEffect, useRef } from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

const SearchBar = ({
  value = "",
  onSearch,
  placeholder = "Search name, group, status, or billing date (YYYY-MM-DD)...",
}) => {
  const [localValue, setLocalValue] = useState(value);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);

  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

  // Sync external changes
  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch && onSearch(localValue);
    }, 300);

    return () => clearTimeout(debounceRef.current);
  }, [localValue, onSearch]);

  // Close calendar on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDatePicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Helper: parse year or partial date from input
  const parseDateFromInput = (val) => {
    const parts = val.trim().split("-");
    const year = parseInt(parts[0], 10);
    const month = parts[1] ? parseInt(parts[1], 10) - 1 : 0; // 0-indexed
    const day = parts[2] ? parseInt(parts[2], 10) : 1;

    if (!isNaN(year)) {
      return new Date(year, month, day);
    }
    return null;
  };

  const handleChange = (e) => {
    const val = e.target.value;
    setLocalValue(val);

    // Show calendar when year or partial date is typed
    if (/^\d{2,4}(-\d{0,2})?$/.test(val.trim())) {
      setShowDatePicker(true);

      const parsed = parseDateFromInput(val);
      setSelectedDate(parsed);
    } else {
      setShowDatePicker(false);
      setSelectedDate(null);
    }
  };

  const clearSearch = () => {
    setLocalValue("");
    setSelectedDate(null);
    setShowDatePicker(false);
    onSearch && onSearch("");
  };

  const selectToday = () => {
    const today = new Date();
    const formatted = today.toLocaleDateString("en-CA"); // YYYY-MM-DD
    setSelectedDate(today);
    setLocalValue(formatted);
    onSearch && onSearch(formatted);
    setShowDatePicker(false); // close calendar
  };

  return (
    <div ref={wrapperRef} className="mb-6 relative">
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
          placeholder={placeholder}
          value={localValue}
          onChange={handleChange}
          className="flex-1 bg-transparent outline-none px-2"
        />

        {localValue && (
          <button
            onClick={clearSearch}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        )}
      </div>

      {/* 📅 Floating Calendar */}
      {showDatePicker && (
        <div className="absolute z-50 mt-2 bg-white shadow-lg rounded">
          <DatePicker
            inline
            selected={selectedDate}
            onChange={(date) => {
              const formatted = date.toLocaleDateString("en-CA");
              setSelectedDate(date);
              setLocalValue(formatted);
              onSearch && onSearch(formatted);
              setShowDatePicker(false);
            }}
          />

          {/* Today Button */}
          <div className="flex justify-end p-2 border-t border-gray-200">
            <button
              onClick={selectToday}
              className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Today
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchBar;
