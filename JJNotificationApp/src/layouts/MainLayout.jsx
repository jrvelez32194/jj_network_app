import { Outlet } from "react-router-dom";
import NavBar from "../components/NavBar";
// import SystemMonitor from "../components/SystemMonitor";

export default function MainLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Global Navigation */}
      <NavBar />
      {/* 🖥 System Monitor below navbar */}
      {/* <div className="w-full flex justify-center px-4 mt-4">
        <SystemMonitor />
      </div> */}
      {/* Page Content */}
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
