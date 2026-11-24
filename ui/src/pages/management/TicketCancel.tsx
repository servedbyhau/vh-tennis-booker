import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { useMachines } from "../../machines";
import { useFormat } from "../../useFormat";
import { machineName } from "../home/ticketText";
import type { CancelPhase } from "./cancelling";
import styles from "./TicketDialog.module.css";

interface TicketCancelProps {
  ticket: Ticket;
  phase: CancelPhase;
  onConfirm: () => void;
  onDismiss: () => void;
}

/** Over the foot of the picture: the question before the cancel, then how it goes. */
export function TicketCancel({ ticket, phase, onConfirm, onDismiss }: TicketCancelProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  if (phase.kind === "idle") {
    return null;
  }
  if (phase.kind === "asking" && ticket.machine === null) {
    return (
      <section className={styles.cancel} aria-label={t("pages.tickets.cancel.button")}>
        <p>{t("pages.tickets.cancel.noMachine")}</p>
        <div className={styles.answers}>
          <button type="button" className={styles.answer} onClick={onDismiss}>
            {t("pages.tickets.close")}
          </button>
        </div>
      </section>
    );
  }
  if (phase.kind === "asking") {
    const name = t("pages.tickets.row", {
      slot: f.slot(ticket.slot),
      court: f.court(ticket.court),
    });
    return (
      <section className={styles.cancel} aria-label={t("pages.tickets.cancel.button")}>
        <p>
          {t("pages.tickets.cancel.question", {
            name,
            day: f.day(ticket.play_date),
            machine: machineName(t, machines, ticket.machine ?? ticket.device),
          })}
        </p>
        <div className={styles.answers}>
          <button type="button" className={styles.answer} onClick={onDismiss}>
            {t("pages.tickets.cancel.no")}
          </button>
          <button type="button" className={`${styles.answer} ${styles.danger}`} onClick={onConfirm}>
            {t("pages.tickets.cancel.yes")}
          </button>
        </div>
      </section>
    );
  }
  return (
    <section className={styles.cancel} aria-label={t("pages.tickets.cancel.button")}>
      <p role="status">
        {phase.kind === "running"
          ? t("pages.tickets.cancel.running")
          : phase.kind === "done"
            ? t("pages.tickets.cancel.done")
            : phase.text}
      </p>
      {phase.kind !== "running" && (
        <div className={styles.answers}>
          <button type="button" className={styles.answer} onClick={onDismiss}>
            {t("pages.tickets.close")}
          </button>
        </div>
      )}
    </section>
  );
}
