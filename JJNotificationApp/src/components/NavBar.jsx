import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react"; // ✅ simple icons

const NavBar = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="bg-blue-900 text-white shadow-md">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex justify-between items-center py-3">
          {/* Logo */}
          <div className="text-lg sm:text-xl font-bold">🔔 JJ Notification</div>

          {/* Desktop Links */}
          <div className="hidden sm:flex gap-6">
            <Link to="/" className="hover:text-gray-300">
              Home
            </Link>
            <Link to="/clients" className="hover:text-gray-300">
              Clients
            </Link>
            <Link to="/templates" className="hover:text-gray-300">
              Templates
            </Link>
            <Link to="/message-logs" className="hover:text-gray-300">
              Message Logs
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="sm:hidden focus:outline-none"
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown */}
      {isOpen && (
        <div className="sm:hidden bg-blue-800 px-4 pb-4 space-y-2">
          <Link
            to="/"
            className="block hover:text-gray-300"
            onClick={() => setIsOpen(false)}
          >
            Home
          </Link>
          <Link
            to="/clients"
            className="block hover:text-gray-300"
            onClick={() => setIsOpen(false)}
          >
            Clients
          </Link>
          <Link
            to="/templates"
            className="block hover:text-gray-300"
            onClick={() => setIsOpen(false)}
          >
            Templates
          </Link>
          <Link
            to="/message-logs"
            className="block hover:text-gray-300"
            onClick={() => setIsOpen(false)}
          >
            Message Logs
          </Link>
        </div>
      )}
    </nav>
  );
};

export default NavBar;
