import { useState } from "react";
import {
  useGetMessengerSettingQuery,
  useUpdateMessengerSettingMutation,
} from "../api/settingsApi";
import { InfoDialog } from "../../components/InfoDialog";
import ConfirmDialog from "../../components/ConfirmDialog";

const MessengerSettingsPage = () => {
  const { data, isLoading } = useGetMessengerSettingQuery();
  const [updateMessengerSetting] = useUpdateMessengerSettingMutation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingValue, setPendingValue] = useState(null);
  const { showToast, Toast } = InfoDialog();

  const enabled = data?.ENABLE_MESSENGER_SEND ?? true;

  const handleToggle = (value) => {
    setPendingValue(value);
    setConfirmOpen(true);
  };

  const confirmToggle = async () => {
    try {
      await updateMessengerSetting({
        ENABLE_MESSENGER_SEND: pendingValue,
      }).unwrap();
      showToast(
        pendingValue
          ? "Messenger sending enabled ✅"
          : "Messenger sending disabled 🚫"
      );
    } catch {
      showToast("Failed to update setting ❌", "error");
    } finally {
      setConfirmOpen(false);
    }
  };

  if (isLoading)
    return (
      <div className="p-4 text-center text-gray-500 animate-pulse">
        Loading Messenger Settings...
      </div>
    );

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <h1 className="text-xl font-bold mb-6">Messenger Settings</h1>

      {/* ⚙️ Main Card */}
      <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="font-semibold text-gray-800">
              Facebook Messenger Sending
            </h2>
            <p className="text-sm text-gray-600 mt-1 max-w-md">
              When enabled, system messages will be sent via Facebook Messenger
              using your Page Access Token. When disabled, all message sends
              will be skipped.
            </p>
          </div>

          {/* ✅ Toggle */}
          <button
            onClick={() => handleToggle(!enabled)}
            className={`px-4 py-2 rounded-lg text-sm font-medium shadow transition-all ${
              enabled
                ? "bg-green-500 text-white hover:bg-green-600"
                : "bg-gray-400 text-white hover:bg-gray-500"
            }`}
          >
            {enabled ? "Enabled ✅" : "Disabled 🚫"}
          </button>
        </div>
      </div>

      {/* ✅ Future Expansion Section Example */}
      {/* <div className="mt-6 bg-white rounded-lg shadow border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="font-semibold text-gray-800">Auto Firewall Block</h2>
            <p className="text-sm text-gray-600 mt-1 max-w-md">
              Automatically block unpaid clients on MikroTik.
            </p>
          </div>
          <button className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-400 text-white">
            Disabled 🚫
          </button>
        </div>
      </div> */}

      {/* ✅ Toast + Confirm */}
      <Toast />
      <ConfirmDialog
        isOpen={confirmOpen}
        message={`Are you sure you want to ${
          pendingValue ? "enable" : "disable"
        } Messenger sending?`}
        onClose={() => setConfirmOpen(false)}
        onConfirm={confirmToggle}
      />
    </div>
  );
};

export default MessengerSettingsPage;
