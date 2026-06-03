import { FormEvent, useState } from "react";

type SystemMessageModalProps = {
  open: boolean;
  onClose: () => void;
  onSend: (message: string) => Promise<void> | void;
  sending?: boolean;
};

export default function SystemMessageModal({
  open,
  onClose,
  onSend,
  sending = false,
}: SystemMessageModalProps) {
  const [message, setMessage] = useState("");

  if (!open) {
    return null;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    await onSend(text);
    setMessage("");
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-5"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[520px] rounded-2xl border border-white/10 bg-[#1b2338] p-5 text-[#ececec]"
        role="dialog"
        aria-labelledby="system-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="mb-2 flex items-center justify-between">
          <h2 id="system-modal-title" className="m-0 text-lg">
            Send system message
          </h2>
          <button
            type="button"
            className="cursor-pointer border-0 bg-transparent text-2xl leading-none text-[#c5c5d2] hover:text-white"
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <p className="mb-3.5 text-sm text-[#8e8ea0]">
          This message is delivered as <strong>system</strong> to the user in the active chat.
        </p>
        <form onSubmit={(event) => void handleSubmit(event)}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Type a system response..."
            rows={5}
            disabled={sending}
            className="w-full resize-y rounded-[10px] border border-white/10 bg-[#2f2f2f] p-3 font-[inherit] text-[#ececec] outline-none focus:border-blue-400/50"
          />
          <div className="mt-3.5 flex justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={sending}
              className="cursor-pointer rounded-lg border border-white/10 bg-transparent px-3.5 py-2 text-[#ececec] disabled:cursor-not-allowed disabled:opacity-55"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!message.trim() || sending}
              className="cursor-pointer rounded-lg border-0 bg-[#052b72] px-3.5 py-2 text-white disabled:cursor-not-allowed disabled:opacity-55"
            >
              {sending ? "Sending..." : "Send as system"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
