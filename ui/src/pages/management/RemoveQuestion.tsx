import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button } from "../../components/Button";
import styles from "./CustomerForms.module.css";

interface RemoveQuestionProps {
  /** What is removed, such as "Xóa Anh An?". */
  title: string;
  /** What is lost with it, one line each. */
  lost: string[];
  pending: boolean;
  error: unknown;
  onRemove: () => void;
  onClose: () => void;
}

/** Ask before a removal, which cannot be taken back: the saved passwords go with it. */
export function RemoveQuestion(props: RemoveQuestionProps) {
  const { title, lost, pending, error, onRemove, onClose } = props;
  const { t } = useTranslation();
  const box = useRef<HTMLDivElement>(null);
  // Away from the button pressed, so a second press removes nothing.
  useEffect(() => {
    box.current?.focus({ preventScroll: true });
    box.current?.scrollIntoView?.({ block: "nearest" });
  }, []);
  return (
    <div ref={box} role="alertdialog" aria-label={title} tabIndex={-1} className={styles.question}>
      <p className={styles.ask}>{title}</p>
      {lost.map((line) => (
        <p key={line} className={styles.lost}>
          {line}
        </p>
      ))}
      <div className={styles.actions}>
        <Button variant="danger" disabled={pending} onClick={onRemove}>
          {t("pages.customers.remove")}
        </Button>
        <Button onClick={onClose}>{t("pages.customers.keep")}</Button>
      </div>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
    </div>
  );
}
