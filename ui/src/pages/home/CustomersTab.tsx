import { type FormEvent, type ReactNode, useState } from "react";
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
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { QueryView } from "../../components/QueryView";
import { EmptyState } from "../../components/States";
import { useMachines } from "../../machines";
import styles from "./CustomersTab.module.css";
import { machineName } from "./ticketText";

/** A phone number as the Vinhomes app takes it: 10 digits from 0. */
const PHONE_PATTERN = "0[0-9]{9}";
const MAX_NAME = 60;
const MAX_NOTE = 500;
const MAX_PASSWORD = 128;

/** The one form open: a customer's or an account's, a new one without `id`. */
type Open =
  | { form: "customer"; id: string | null }
  | { form: "account"; customerId: string; id: string | null };

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
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }
  return (
    <form className={styles.form} aria-label={title} onSubmit={submit}>
      {children}
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={pending}>
          {t("pages.customers.save")}
        </Button>
        <Button onClick={onClose}>{t("pages.customers.cancel")}</Button>
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
    return <p className={styles.note}>{t("pages.customers.attached", { machine })}</p>;
  }
  return (
    <div className={styles.actions}>
      {asked ? (
        <>
          <Button disabled={remove.isPending} onClick={remove.mutate}>
            {t("pages.customers.removeSure")}
          </Button>
          <Button onClick={() => setAsked(false)}>{t("pages.customers.keep")}</Button>
        </>
      ) : (
        <Button onClick={() => setAsked(true)}>{t("pages.customers.remove")}</Button>
      )}
      {remove.error !== null && (
        <p role="alert" className={styles.error}>
          {errorMessage(t, remove.error)}
        </p>
      )}
    </div>
  );
}

function CustomerForm({ customer, onClose }: { customer: Customer | null; onClose: () => void }) {
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
      title={t(customer === null ? "pages.customers.add" : "pages.customers.edit")}
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
function AccountForm({ customerId, account, onClose }: AccountFormProps) {
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
      title={t(account === null ? "pages.customers.addAccount" : "pages.customers.edit")}
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
      <p className={styles.note}>{t("pages.customers.private")}</p>
    </EditForm>
  );
}

/** An account in one line: its number, its label and the machine it is attached to. */
function AccountRow({ account, onEdit }: { account: CustomerAccount; onEdit: () => void }) {
  const { t } = useTranslation();
  const machines = useMachines();
  return (
    <div className={styles.account}>
      <span className={styles.phone}>{account.phone ?? t("pages.customers.noLogin")}</span>
      <span className={styles.accountLabel}>{account.label}</span>
      {account.device !== null && (
        <span className={styles.machine}>{machineName(t, machines, account.device)}</span>
      )}
      <Button className={styles.small} onClick={onEdit}>
        {t("pages.customers.edit")}
      </Button>
    </div>
  );
}

interface CustomerSectionProps {
  customer: Customer;
  open: Open | null;
  onOpen: (open: Open | null) => void;
}

function CustomerSection({ customer, open, onOpen }: CustomerSectionProps) {
  const { t } = useTranslation();
  const close = () => onOpen(null);
  const account = open?.form === "account" && open.customerId === customer.id ? open : null;
  return (
    <section aria-label={customer.name} className={styles.customer}>
      {open?.form === "customer" && open.id === customer.id ? (
        <CustomerForm customer={customer} onClose={close} />
      ) : (
        <div className={styles.head}>
          <div>
            <h3 className={styles.name}>{customer.name}</h3>
            {customer.note !== "" && <p className={styles.note}>{customer.note}</p>}
          </div>
          <Button
            className={styles.small}
            onClick={() => onOpen({ form: "customer", id: customer.id })}
          >
            {t("pages.customers.edit")}
          </Button>
        </div>
      )}
      {customer.accounts.length === 0 && (
        <p className={styles.note}>{t("pages.customers.noAccounts")}</p>
      )}
      <ul className={styles.accounts}>
        {customer.accounts.map((item) => (
          <li key={item.id}>
            {account?.id === item.id ? (
              <AccountForm customerId={customer.id} account={item} onClose={close} />
            ) : (
              <AccountRow
                account={item}
                onEdit={() => onOpen({ form: "account", customerId: customer.id, id: item.id })}
              />
            )}
          </li>
        ))}
      </ul>
      {account !== null && account.id === null ? (
        <AccountForm customerId={customer.id} account={null} onClose={close} />
      ) : (
        <Button
          className={styles.small}
          onClick={() => onOpen({ form: "account", customerId: customer.id, id: null })}
        >
          {t("pages.customers.addAccount")}
        </Button>
      )}
    </section>
  );
}

/**
 * The customers and the Vinhomes accounts each one gave. The phone numbers show with their
 * middle hidden and a password never again; the Setup tab attaches an account to a machine.
 */
export function CustomersTab() {
  const { t } = useTranslation();
  const customers = useCustomers();
  const [open, setOpen] = useState<Open | null>(null);
  return (
    <div className={styles.tab}>
      <QueryView query={customers}>
        {(list) => (
          <>
            {open?.form === "customer" && open.id === null ? (
              <CustomerForm customer={null} onClose={() => setOpen(null)} />
            ) : (
              <div className={styles.top}>
                <Button variant="primary" onClick={() => setOpen({ form: "customer", id: null })}>
                  {t("pages.customers.add")}
                </Button>
              </div>
            )}
            {list.length === 0 && <EmptyState>{t("pages.customers.empty")}</EmptyState>}
            {list.map((customer) => (
              <CustomerSection key={customer.id} customer={customer} open={open} onOpen={setOpen} />
            ))}
          </>
        )}
      </QueryView>
    </div>
  );
}
