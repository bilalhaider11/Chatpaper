type CancelSubscriptionModalProps = {
  open: boolean;
  mode: "confirm" | "success" | "error";
  title: string;
  message: string;
  loading?: boolean;
  onClose: () => void;
  onConfirm?: () => void;
};

export default function CancelSubscriptionModal({
  open,
  mode,
  title,
  message,
  loading = false,
  onClose,
  onConfirm,
}: CancelSubscriptionModalProps) {
  if (!open) return null;

  return (
    <div className="pricing-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="pricing-modal"
        role="dialog"
        aria-labelledby="pricing-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="pricing-modal-header">
          <h2 id="pricing-modal-title">{title}</h2>
          <button type="button" className="pricing-modal-close" onClick={onClose} disabled={loading}>
            ×
          </button>
        </header>
        <p className="pricing-modal-message">{message}</p>
        <div className="pricing-modal-actions">
          {mode === "confirm" ? (
            <>
              <button type="button" onClick={onClose} disabled={loading}>
                Keep subscription
              </button>
              <button
                type="button"
                className="pricing-modal-danger"
                onClick={onConfirm}
                disabled={loading}
              >
                {loading ? "Canceling…" : "Yes, cancel plan"}
              </button>
            </>
          ) : (
            <button type="button" className="pricing-modal-primary" onClick={onClose}>
              Got it
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
