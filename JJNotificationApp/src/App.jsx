import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import ClientsPage from "./features/clients/ClientsPage";
import TemplatesPage from "./features/templates/TemplatesPage";
import MessageLogs from "./features/messages/MessageLogs";
import NotFound from "./components/NotFound";
import "./index.css";

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<MainLayout />}>
          <Route
            path="/"
            element={
              <h1 className="text-3xl font-bold text-center">
                Welcome to JJ Notification App 🔔
              </h1>
            }
          />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/message-logs" element={<MessageLogs />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
