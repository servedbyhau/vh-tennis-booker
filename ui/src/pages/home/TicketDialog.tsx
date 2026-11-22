import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { Button } from "../../components/Button";
import { ButtonLink } from "../../components/ButtonLink";
import { photoFileName, photoUrl } from "../../tickets";
import { useFormat } from "../../useFormat";
import styles from "./TicketDialog.module.css";

interface TicketDialogProps {
  /** The tickets listed, in their order. */
  tickets: readonly Ticket[];
  /** Which of them shows. */
  place: number;
  onPlace: (place: number) => void;
  onClose: () => void;
}

/**
 * One ticket's picture over the page, with a button to save it and the ones before and after it
 * in the list. The arrow keys move between them; Escape, or a press beside it, closes it, and
 * the focus returns to where it was.
 */
export function TicketDialog({ tickets, place, onPlace, onClose }: TicketDialogProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const dialog = useRef<HTMLDivElement>(null);
  /** The ticket whose picture did not open. */
  const [failedCode, setFailedCode] = useState<string | null>(null);
  const ticket = tickets[place];

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
        if (event.target === event.currentTarget) {
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
        <button
          type="button"
          aria-label={t("pages.tickets.previous")}
          disabled={place === 0}
          className={styles.move}
          onClick={() => onPlace(place - 1)}
        >
          ←
        </button>
        <div className={styles.sheet}>
          <div className={styles.bar}>
            <span className={styles.place}>
              {t("pages.tickets.place", { place: place + 1, total: tickets.length })}
            </span>
            {hasPicture && (
              <ButtonLink
                variant="primary"
                href={photoUrl(ticket)}
                download={photoFileName(ticket, court)}
              >
                {t("pages.tickets.save")}
              </ButtonLink>
            )}
            <Button onClick={onClose}>{t("pages.tickets.close")}</Button>
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
              {t(failed ? "pages.tickets.photoFailed" : "pages.tickets.photoNone")}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-label={t("pages.tickets.next")}
          disabled={place === tickets.length - 1}
          className={styles.move}
          onClick={() => onPlace(place + 1)}
        >
          →
        </button>
      </div>
    </div>,
    document.body,
  );
}
