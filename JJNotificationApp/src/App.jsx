import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import ClientsPage from "./features/clients/ClientsPage";
import TemplatesPage from "./features/templates/TemplatesPage";
import MessageLogs from "./features/messages/MessageLogs";
import SystemMonitor from "./features/systemMonitor/SystemMonitor";
import MessengerSettingsPage from "./features/settings/MessengerSettingsPage"; // ✅ NEW
import NotFound from "./components/NotFound";
import "./index.css";

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<MainLayout />}>
          {/* 🏠 Home Page — with System Monitor */}
          <Route
            path="/"
            element={
              <div className="flex flex-col items-center text-center gap-6 mt-8">
                <h1 className="text-3xl font-bold">
                  Welcome to JJ Notification App 🔔
                </h1>
                {/* ✅ System Monitor displayed only on Home */}
                <div className="w-full flex justify-center px-4">
                  <SystemMonitor />
                </div>
              </div>
            }
          />

          {/* 📋 Core Pages */}
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/message-logs" element={<MessageLogs />} />
          <Route
            path="/settings/messenger"
            element={<MessengerSettingsPage />}
          />

          {/* ❌ Fallback */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
