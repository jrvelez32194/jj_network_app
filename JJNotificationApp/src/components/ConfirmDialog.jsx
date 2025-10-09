import { Dialog } from "@headlessui/react";

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
}) {
  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div className="fixed inset-0 bg-black/40" aria-hidden="true" />
      <div className="bg-white rounded-lg p-6 shadow-lg z-50 w-full max-w-md">
        <Dialog.Title className="text-lg font-bold mb-2">{title}</Dialog.Title>
        <Dialog.Description className="text-gray-600 mb-4">
          {message}
        </Dialog.Description>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-300 text-gray-800 rounded hover:bg-gray-400"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Confirm
          </button>
        </div>
      </div>
    </Dialog>
  );
}
