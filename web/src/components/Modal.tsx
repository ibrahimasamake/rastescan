import { useEffect, useRef, type ReactNode } from "react";
import { useI18n } from "../i18n";

/** A popup built on the native <dialog>: it traps focus, closes with Esc, and closes on a click outside the card. */
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  return (
    <dialog ref={ref} className="modal" aria-label={title} onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <div className="modal-body">
        <button className="modal-x" onClick={onClose} aria-label={t("common.close")}>×</button>
        {children}
      </div>
    </dialog>
  );
}
