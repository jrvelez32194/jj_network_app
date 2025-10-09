import { Outlet } from "react-router-dom";
import NavBar from "../components/NavBar";

export default function MainLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Global Navigation */}
      <NavBar />

      {/* Page Content */}
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
