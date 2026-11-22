import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { Button } from "../../components/Button";
import { useMachines } from "../../machines";
import { photoUrl } from "../../tickets";
import { useFormat } from "../../useFormat";
import styles from "./TicketDialog.module.css";
import { TicketStamp } from "./TicketStamp";
import { machineName } from "./ticketText";

/** A ticket's picture, or why there is none. */
function TicketPhoto({ ticket, name }: { ticket: Ticket; name: string }) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState(false);
  if (!ticket.has_photo || failed) {
    return (
      <p className={styles.noPhoto}>
        {t(failed ? "pages.tickets.photoFailed" : "pages.tickets.photoNone")}
      </p>
    );
  }
  return (
    <img
      src={photoUrl(ticket)}
      alt={t("pages.tickets.photo", { name })}
      className={styles.photo}
      onError={() => setFailed(true)}
    />
  );
}

interface TicketDialogProps {
  /** The tickets listed, in their order. */
  tickets: readonly Ticket[];
  /** Which of them shows. */
  place: number;
  onPlace: (place: number) => void;
  onClose: () => void;
}

/**
 * One ticket over the page: its picture, what is known of it, and the ones before and after it
 * in the list. The arrow keys move between them; Escape, or a press beside it, closes it, and
 * the focus returns to where it was.
 */
export function TicketDialog({ tickets, place, onPlace, onClose }: TicketDialogProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  const dialog = useRef<HTMLDivElement>(null);
  const ticket = tickets[place];

  useEffect(() => {
    const before = document.activeElement;
    dialog.current?.focus();
    return () => {
      if (before instanceof HTMLElement) {
        before.focus();
      }
    };
  }, []);

  if (ticket === undefined) {
    return null;
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      onClose();
    } else if (event.key === "ArrowLeft" && place > 0) {
      onPlace(place - 1);
    } else if (event.key === "ArrowRight" && place < tickets.length - 1) {
      onPlace(place + 1);
    } else if (event.key === "Tab") {
      keepFocus(event);
    }
  }

  /** Keep Tab within the dialog: the page behind it is not to be used meanwhile. */
  function keepFocus(event: KeyboardEvent) {
    const buttons = [
      ...(dialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled)") ?? []),
    ];
    const edge = event.shiftKey ? buttons[0] : buttons.at(-1);
    const target = event.shiftKey ? buttons.at(-1) : buttons[0];
    const active = document.activeElement;
    if (active === edge || (event.shiftKey && active === dialog.current)) {
      event.preventDefault();
      target?.focus();
    }
  }

  const name = t("pages.tickets.row", { slot: f.slot(ticket.slot), court: f.court(ticket.court) });
  const facts: [string, string][] = [
    [t("pages.tickets.facts.day"), f.day(ticket.play_date)],
    [t("pages.tickets.facts.slot"), f.slot(ticket.slot)],
    [t("pages.tickets.facts.court"), f.court(ticket.court)],
    [t("pages.tickets.facts.machine"), machineName(t, machines, ticket.device)],
    [t("pages.tickets.facts.code"), ticket.code],
  ];
  if (ticket.created_at !== null) {
    facts.push([
      t("pages.tickets.facts.created"),
      `${f.time(ticket.created_at)} ${f.shortDate(ticket.created_at)}`,
    ]);
  }
  return createPortal(
    <div
      className={styles.backdrop}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ticket-title"
        tabIndex={-1}
        className={styles.dialog}
        onKeyDown={onKeyDown}
      >
        <div className={styles.picture}>
          <TicketPhoto key={ticket.code} ticket={ticket} name={name} />
        </div>
        <div className={styles.side}>
          <h2 id="ticket-title" className={styles.title}>
            {name}
          </h2>
          <div>
            <TicketStamp ticket={ticket} />
          </div>
          <dl className={styles.facts}>
            {facts.map(([label, value]) => (
              <div key={label} className={styles.fact}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.note}>
            {t("pages.tickets.seen", {
              time: f.time(ticket.seen_at),
              day: f.shortDate(ticket.seen_at),
            })}
          </p>
          <div className={styles.actions}>
            <span className={styles.place}>
              {t("pages.tickets.place", { place: place + 1, total: tickets.length })}
            </span>
            <div className={styles.move}>
              <Button disabled={place === 0} onClick={() => onPlace(place - 1)}>
                {t("pages.tickets.previous")}
              </Button>
              <Button disabled={place === tickets.length - 1} onClick={() => onPlace(place + 1)}>
                {t("pages.tickets.next")}
              </Button>
            </div>
            <Button variant="primary" onClick={onClose}>
              {t("pages.tickets.close")}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
