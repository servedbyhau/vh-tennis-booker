import { type KeyboardEvent, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import type { CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { useMachines } from "../../machines";
import { machineName } from "../home/ticketText";
import styles from "./RemoveQuestion.module.css";

interface RemoveQuestionProps {
  /** What is removed, such as "Xóa Anh An?". */
  title: string;
  /** The accounts lost with their passwords; more than the one named are listed. */
  accounts: readonly CustomerAccount[];
  /** Whether the title names the account lost, which is then not listed again. */
  named?: boolean;
  pending: boolean;
  error: unknown;
  onRemove: () => void;
  onClose: () => void;
}

/**
 * Ask over the page before a removal, which cannot be taken back: what is lost, and which machines
 * are left without an account. Keeping it is the choice in focus, and Escape keeps it too; a press
 * beside it does nothing.
 */
export function RemoveQuestion(props: RemoveQuestionProps) {
  const { title, accounts, named = false, pending, error, onRemove, onClose } = props;
  const { t } = useTranslation();
  const id = useId();
  const machines = useMachines();
  const box = useRef<HTMLDivElement>(null);
  const keep = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const before = document.activeElement;
    keep.current?.focus();
    return () => {
      if (before instanceof HTMLElement) {
        before.focus();
      }
    };
  }, []);

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      onClose();
    } else if (event.key === "Tab") {
      // The page behind it is not to be used meanwhile.
      const controls = [...(box.current?.querySelectorAll("button:not(:disabled)") ?? [])];
      const edge = event.shiftKey ? controls[0] : controls.at(-1);
      if (document.activeElement === edge) {
        event.preventDefault();
        const other = event.shiftKey ? controls.at(-1) : controls[0];
        (other as HTMLElement | undefined)?.focus();
      }
    }
  }

  const used = accounts.flatMap(({ device }) =>
    device === null ? [] : machineName(t, machines, device),
  );
  return createPortal(
    <div className={styles.backdrop}>
      <div
        ref={box}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={`${id}-lost`}
        className={styles.question}
        onKeyDown={onKeyDown}
      >
        <span className={styles.icon}>
          <Icon name="remove" />
        </span>
        <h2 id={`${id}-title`} className={styles.title}>
          {title}
        </h2>
        <div id={`${id}-lost`} className={styles.lost}>
          {!named && accounts.length > 0 && (
            <>
              <p>{t("pages.customers.lostAccounts", { count: accounts.length })}</p>
              <ul className={styles.accounts}>
                {accounts.map((account) => (
                  <li key={account.id}>
                    <span className={styles.phone}>
                      {account.phone ?? t("pages.customers.noLogin")}
                    </span>
                    {account.label !== "" && ` · ${account.label}`}
                  </li>
                ))}
              </ul>
            </>
          )}
          <p>
            {t(accounts.length > 0 ? "pages.customers.lostPasswords" : "pages.customers.lostFacts")}
          </p>
          {used.length > 0 && (
            <p className={styles.used}>
              {t("pages.customers.inUse", { machines: used.join(", ") })}
            </p>
          )}
        </div>
        {error !== null && (
          <p role="alert" className={styles.error}>
            {errorMessage(t, error)}
          </p>
        )}
        <div className={styles.actions}>
          <Button ref={keep} onClick={onClose}>
            {t("pages.customers.keep")}
          </Button>
          <Button variant="danger" disabled={pending} onClick={onRemove}>
            <Icon name="remove" />
            {t("pages.customers.remove")}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
