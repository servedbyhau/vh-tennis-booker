import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { Icon } from "../../components/Icon";
import { copyPicture, photoFileName, photoUrl } from "../../tickets";
import { useFormat } from "../../useFormat";
import { useMarkSent } from "../../api/mutations";
import { TicketCancel } from "./TicketCancel";
import { cancellable, useTicketCancel } from "./cancelling";
import styles from "./TicketDialog.module.css";

/** How long it shows how a copy went. */
const NOTICE_MS = 2500;

interface TicketDialogProps {
  /** The tickets listed, in their order. */
  tickets: readonly Ticket[];
  /** Which of them shows. */
  place: number;
  onPlace: (place: number) => void;
  onClose: () => void;
}

/**
 * One ticket's picture over the page, with buttons to save and to copy it, to cancel it in the app
 * while its slot is still to come, and the ones before and after it in the list. The arrow keys
 * move between them; Escape, or a press beside it, closes it, and the focus returns to where it
 * was.
 */
export function TicketDialog({ tickets, place, onPlace, onClose }: TicketDialogProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const dialog = useRef<HTMLDivElement>(null);
  /** The ticket whose picture did not open. */
  const [failedCode, setFailedCode] = useState<string | null>(null);
  /** How the last copy went, shown for a moment. */
  const [copy, setCopy] = useState<"copied" | "copyFailed" | null>(null);
  const ticket = tickets[place];
  const cancel = useTicketCancel(ticket);
  const mark = useMarkSent();

  useEffect(() => {
    const before = document.activeElement;
    return () => {
      if (before instanceof HTMLElement) {
        before.focus();
      }
    };
  }, []);

  // At first, and when a move takes the control pressed away: the keys work inside only.
  useEffect(() => {
    const active = document.activeElement;
    if (!dialog.current?.contains(active) || active?.matches(":disabled")) {
      dialog.current?.focus();
    }
  }, [place]);

  useEffect(() => {
    const timer = copy === null ? undefined : setTimeout(() => setCopy(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [copy]);

  if (ticket === undefined) {
    return null;
  }

  function onCopy(url: string) {
    setCopy(null);
    copyPicture(url).then(
      () => setCopy("copied"),
      () => setCopy("copyFailed"),
    );
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
    const controls = [
      ...(dialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled), a[href]") ?? []),
    ];
    const edge = event.shiftKey ? controls[0] : controls.at(-1);
    const target = event.shiftKey ? controls.at(-1) : controls[0];
    const active = document.activeElement;
    if (active === edge || (event.shiftKey && active === dialog.current)) {
      event.preventDefault();
      target?.focus();
    }
  }

  const court = f.court(ticket.court);
  const name = t("pages.tickets.row", { slot: f.slot(ticket.slot), court });
  const failed = failedCode === ticket.code;
  const hasPicture = ticket.has_photo && !failed;
  return createPortal(
    <div
      className={styles.backdrop}
      onClick={(event) => {
        // Beside the picture and the buttons, between them too.
        if (
          event.target instanceof Element &&
          !event.target.closest("img, p, a, button, section")
        ) {
          onClose();
        }
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label={name}
        tabIndex={-1}
        className={styles.dialog}
        onKeyDown={onKeyDown}
      >
        <div className={styles.side}>
          <div className={styles.top}>
            {tickets.length > 1 && (
              <span className={styles.place}>
                {t("pages.tickets.place", { place: place + 1, total: tickets.length })}
              </span>
            )}
          </div>
          <button
            type="button"
            aria-label={t("pages.tickets.previous")}
            title={t("pages.tickets.previous")}
            disabled={place === 0}
            className={styles.round}
            onClick={() => onPlace(place - 1)}
          >
            <Icon name="back" />
          </button>
        </div>
        {hasPicture ? (
          <img
            // An element per ticket: the last one's picture never shows while this one loads.
            key={ticket.code}
            src={photoUrl(ticket)}
            alt={t("pages.tickets.photo", { name })}
            className={styles.photo}
            onError={() => setFailedCode(ticket.code)}
          />
        ) : (
          <p className={styles.noPhoto}>
            <Icon name="picture" />
            {t(failed ? "pages.tickets.photoFailed" : "pages.tickets.photoNone")}
          </p>
        )}
        <div className={styles.side}>
          <div className={styles.top}>
            <button
              type="button"
              aria-label={t("pages.tickets.close")}
              title={t("pages.tickets.close")}
              className={styles.round}
              onClick={onClose}
            >
              <Icon name="close" />
            </button>
            {hasPicture && (
              <a
                href={photoUrl(ticket)}
                download={photoFileName(ticket, court)}
                aria-label={t("pages.tickets.save")}
                title={t("pages.tickets.save")}
                className={`${styles.round} ${styles.save}`}
              >
                <Icon name="save" />
              </a>
            )}
            {hasPicture && (
              <button
                type="button"
                aria-label={t("pages.tickets.copy")}
                title={t("pages.tickets.copy")}
                className={`${styles.round} ${styles.save}`}
                onClick={() => onCopy(photoUrl(ticket))}
              >
                <Icon name="copy" />
              </button>
            )}
            <button
              type="button"
              aria-pressed={ticket.sent_at !== null}
              aria-label={t("pages.tickets.sent")}
              title={t(
                ticket.sent_at === null ? "pages.tickets.markSent" : "pages.tickets.sentMark",
              )}
              disabled={mark.isPending}
              className={ticket.sent_at === null ? styles.round : `${styles.round} ${styles.save}`}
              onClick={() => mark.mutate({ code: ticket.code, sent: ticket.sent_at === null })}
            >
              <Icon name="check" />
            </button>
            {cancellable(ticket) && (
              <button
                type="button"
                aria-label={t("pages.tickets.cancel.button")}
                title={t("pages.tickets.cancel.button")}
                disabled={cancel.phase.kind === "running"}
                className={styles.round}
                onClick={cancel.ask}
              >
                <Icon name="cancel" />
              </button>
            )}
          </div>
          <button
            type="button"
            aria-label={t("pages.tickets.next")}
            title={t("pages.tickets.next")}
            disabled={place === tickets.length - 1}
            className={styles.round}
            onClick={() => onPlace(place + 1)}
          >
            <Icon name="forward" />
          </button>
        </div>
        <p role="status" className={styles.notice}>
          {copy !== null && t(`pages.tickets.${copy}`)}
        </p>
        <TicketCancel
          ticket={ticket}
          phase={cancel.phase}
          onConfirm={cancel.confirm}
          onDismiss={cancel.dismiss}
        />
      </div>
    </div>,
    document.body,
  );
}
