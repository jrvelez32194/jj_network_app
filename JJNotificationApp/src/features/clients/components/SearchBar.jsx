import React, { Component } from "react";

class SearchBar extends Component {
  handleChange = (e) => {
    const { onSearch } = this.props;
    onSearch && onSearch(e.target.value);
  };

  clearSearch = () => {
    const { onSearch } = this.props;
    onSearch && onSearch("");
  };

  render() {
    const { value, placeholder = "Search clients..." } = this.props;

    return (
      <div className="mb-6">
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
            value={value}
            onChange={this.handleChange}
            className="flex-1 bg-transparent outline-none px-2"
          />

          {value && (
            <button
              onClick={this.clearSearch}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    );
  }
}

export default SearchBar;
