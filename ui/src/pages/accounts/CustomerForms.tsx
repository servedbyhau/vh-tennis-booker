import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import {
  useAddAccount,
  useAddCustomer,
  useChangeAccount,
  useChangeCustomer,
  useRemoveAccount,
  useRemoveCustomer,
} from "../../api/mutations";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { useMachines } from "../../machines";
import styles from "./CustomerForms.module.css";
import { machineName } from "../home/ticketText";

/** A phone number as the Vinhomes app takes it: 10 digits from 0. */
const PHONE_PATTERN = "0[0-9]{9}";
const MAX_NAME = 60;
const MAX_NOTE = 500;
const MAX_PASSWORD = 128;

interface FieldProps {
  label: string;
  children: ReactNode;
}

function Field({ label, children }: FieldProps) {
  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      {children}
    </label>
  );
}

interface FormProps {
  title: string;
  pending: boolean;
  error: unknown;
  onSave: () => void;
  onClose: () => void;
  /** What removes the record, under the fields. */
  remove?: ReactNode;
  children: ReactNode;
}

/** The frame of both forms: the fields, Save and Cancel, and why a save failed. */
function EditForm({ title, pending, error, onSave, onClose, remove, children }: FormProps) {
  const { t } = useTranslation();
  const form = useRef<HTMLFormElement>(null);
  // It may open below the window's edge.
  useEffect(() => {
    form.current?.querySelector("input")?.focus({ preventScroll: true });
    form.current?.scrollIntoView?.({ block: "nearest" });
  }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }
  return (
    <form ref={form} className={styles.form} aria-label={title} onSubmit={submit}>
      <div className={styles.fields}>{children}</div>
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={pending}>
          {t("pages.accounts.save")}
        </Button>
        <Button onClick={onClose}>{t("pages.accounts.cancel")}</Button>
      </div>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
      {remove}
    </form>
  );
}

interface RemoveProps {
  /** The machine that keeps the record from being removed, if any. */
  machine: string | null;
  remove: { mutate: () => void; isPending: boolean; error: unknown };
}

/** A removal in two presses: it cannot be taken back, and the password is gone with it. */
function Remove({ machine, remove }: RemoveProps) {
  const { t } = useTranslation();
  const [asked, setAsked] = useState(false);
  if (machine !== null) {
    return <p className={styles.note}>{t("pages.accounts.attached", { machine })}</p>;
  }
  return (
    <div className={styles.actions}>
      {asked ? (
        <>
          <Button disabled={remove.isPending} onClick={remove.mutate}>
            {t("pages.accounts.removeSure")}
          </Button>
          <Button onClick={() => setAsked(false)}>{t("pages.accounts.keep")}</Button>
        </>
      ) : (
        <Button onClick={() => setAsked(true)}>{t("pages.accounts.remove")}</Button>
      )}
      {remove.error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, remove.error)}
        </p>
      )}
    </div>
  );
}

/** A customer's name and note. */
export function CustomerForm({
  customer,
  onClose,
}: {
  customer: Customer | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const machines = useMachines();
  const add = useAddCustomer();
  const change = useChangeCustomer();
  const remove = useRemoveCustomer();
  const [name, setName] = useState(customer?.name ?? "");
  const [note, setNote] = useState(customer?.note ?? "");
  const save = customer === null ? add : change;
  const device = customer?.accounts.find((account) => account.device !== null)?.device ?? null;

  function onSave() {
    const fields = { name, note };
    if (customer === null) {
      add.mutate(fields, { onSuccess: onClose });
    } else {
      change.mutate({ id: customer.id, fields }, { onSuccess: onClose });
    }
  }

  return (
    <EditForm
      title={t(customer === null ? "pages.accounts.add" : "pages.accounts.editCustomer")}
      pending={save.isPending}
      error={save.error}
      onSave={onSave}
      onClose={onClose}
      remove={
        customer !== null && (
          <Remove
            machine={device === null ? null : machineName(t, machines, device)}
            remove={{
              mutate: () => remove.mutate(customer.id, { onSuccess: onClose }),
              isPending: remove.isPending,
              error: remove.error,
            }}
          />
        )
      }
    >
      <Field label={t("pages.accounts.name")}>
        <input
          required
          pattern=".*\S.*"
          maxLength={MAX_NAME}
          autoComplete="off"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </Field>
      <Field label={t("pages.accounts.note")}>
        <input
          maxLength={MAX_NOTE}
          autoComplete="off"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </Field>
    </EditForm>
  );
}

interface AccountFormProps {
  customerId: string;
  account: CustomerAccount | null;
  onClose: () => void;
}

/** An account's login and label; of one already saved the phone stays, the password is kept. */
export function AccountForm({ customerId, account, onClose }: AccountFormProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  const add = useAddAccount();
  const change = useChangeAccount();
  const remove = useRemoveAccount();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [label, setLabel] = useState(account?.label ?? "");
  const save = account === null ? add : change;

  function onSave() {
    if (account === null) {
      add.mutate({ customerId, account: { phone, password, label } }, { onSuccess: onClose });
    } else {
      const fields = { label, password: password === "" ? null : password };
      change.mutate({ id: account.id, fields }, { onSuccess: onClose });
    }
  }

  return (
    <EditForm
      title={t(account === null ? "pages.accounts.addAccount" : "pages.accounts.edit")}
      pending={save.isPending}
      error={save.error}
      onSave={onSave}
      onClose={onClose}
      remove={
        account !== null && (
          <Remove
            machine={account.device === null ? null : machineName(t, machines, account.device)}
            remove={{
              mutate: () => remove.mutate(account.id, { onSuccess: onClose }),
              isPending: remove.isPending,
              error: remove.error,
            }}
          />
        )
      }
    >
      {account === null && (
        <Field label={t("pages.accounts.phone")}>
          <input
            type="tel"
            inputMode="numeric"
            autoComplete="off"
            required
            pattern={PHONE_PATTERN}
            maxLength={10}
            value={phone}
            onChange={(event) => setPhone(event.target.value.trim())}
          />
        </Field>
      )}
      <Field label={t(account === null ? "pages.accounts.password" : "pages.accounts.newPassword")}>
        <input
          type="password"
          autoComplete="new-password"
          required={account === null}
          maxLength={MAX_PASSWORD}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <Field label={t("pages.accounts.label")}>
        <input
          maxLength={MAX_NAME}
          autoComplete="off"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
      </Field>
      <p className={styles.note}>{t("pages.accounts.private")}</p>
    </EditForm>
  );
}
