import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import {
  useAddAccount,
  useAddCustomer,
  useChangeAccount,
  useChangeCustomer,
} from "../../api/mutations";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import styles from "./CustomerForms.module.css";

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
  children: ReactNode;
}

/** The frame of both forms: the fields, Save and Cancel, and why a save failed. */
function EditForm({ title, pending, error, onSave, onClose, children }: FormProps) {
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
          <Icon name="check" />
          {t("pages.customers.save")}
        </Button>
        <Button onClick={onClose}>
          <Icon name="close" />
          {t("pages.customers.cancel")}
        </Button>
      </div>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
    </form>
  );
}

interface CustomerFormProps {
  customer: Customer | null;
  onClose: () => void;
  /** Gets a new customer once saved, in place of `onClose`. */
  onSaved?: (customer: Customer) => void;
}

/** Who a customer is. */
export function CustomerForm({ customer, onClose, onSaved }: CustomerFormProps) {
  const { t } = useTranslation();
  const add = useAddCustomer();
  const change = useChangeCustomer();
  const [name, setName] = useState(customer?.name ?? "");
  const [representative, setRepresentative] = useState(customer?.representative ?? "");
  const [contact, setContact] = useState(customer?.contact ?? "");
  const [note, setNote] = useState(customer?.note ?? "");
  const save = customer === null ? add : change;

  function onSave() {
    const fields = { name, representative, contact, note };
    if (customer === null) {
      add.mutate(fields, { onSuccess: onSaved ?? onClose });
    } else {
      change.mutate({ id: customer.id, fields }, { onSuccess: onClose });
    }
  }

  return (
    <EditForm
      title={t(customer === null ? "pages.customers.add" : "pages.customers.editCustomer")}
      pending={save.isPending}
      error={save.error}
      onSave={onSave}
      onClose={onClose}
    >
      <Field label={t("pages.customers.name")}>
        <input
          required
          pattern=".*\S.*"
          maxLength={MAX_NAME}
          autoComplete="off"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </Field>
      <Field label={t("pages.customers.representative")}>
        <input
          maxLength={MAX_NAME}
          autoComplete="off"
          value={representative}
          onChange={(event) => setRepresentative(event.target.value)}
        />
      </Field>
      <Field label={t("pages.customers.contact")}>
        <input
          maxLength={MAX_NAME}
          autoComplete="off"
          value={contact}
          onChange={(event) => setContact(event.target.value)}
        />
      </Field>
      <Field label={t("pages.customers.note")}>
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
  const add = useAddAccount();
  const change = useChangeAccount();
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
      title={t(account === null ? "pages.customers.addAccount" : "pages.customers.edit")}
      pending={save.isPending}
      error={save.error}
      onSave={onSave}
      onClose={onClose}
    >
      {account === null && (
        <Field label={t("pages.customers.phone")}>
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
      <Field
        label={t(account === null ? "pages.customers.password" : "pages.customers.newPassword")}
      >
        <input
          type="password"
          autoComplete="new-password"
          required={account === null}
          maxLength={MAX_PASSWORD}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <Field label={t("pages.customers.label")}>
        <input
          maxLength={MAX_NAME}
          autoComplete="off"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
      </Field>
      <p className={styles.note}>
        <Icon name="lock" />
        {t("pages.customers.private")}
      </p>
    </EditForm>
  );
}
