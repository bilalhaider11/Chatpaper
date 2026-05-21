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
    <div className="system-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="system-modal"
        role="dialog"
        aria-labelledby="system-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="system-modal-header">
          <h2 id="system-modal-title">Send system message</h2>
          <button type="button" className="system-modal-close" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="system-modal-subtitle">
          This message is delivered as <strong>system</strong> to the user in the active chat.
        </p>
        <form onSubmit={(event) => void handleSubmit(event)}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Type a system response..."
            rows={5}
            disabled={sending}
          />
          <div className="system-modal-actions">
            <button type="button" onClick={onClose} disabled={sending}>
              Cancel
            </button>
            <button type="submit" disabled={!message.trim() || sending}>
              {sending ? "Sending..." : "Send as system"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
