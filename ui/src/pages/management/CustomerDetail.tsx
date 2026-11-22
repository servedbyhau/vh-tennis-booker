import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useRemoveAccount, useRemoveCustomer } from "../../api/mutations";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { useMachines } from "../../machines";
import { machineName } from "../home/ticketText";
import styles from "./CustomerDetail.module.css";
import { AccountForm, CustomerForm } from "./CustomerForms";
import { RemoveQuestion } from "./RemoveQuestion";

/** What is open: the customer's form, an account's (a new one without `id`), or a removal. */
type Open =
  | { form: "customer" }
  | { form: "account"; id: string | null }
  | { form: "removeCustomer" }
  | { form: "removeAccount"; id: string };

/** Who the customer is; what is not known is left out. */
function Facts({ customer }: { customer: Customer }) {
  const { t } = useTranslation();
  const facts = [
    [t("pages.customers.representative"), customer.representative],
    [t("pages.customers.contact"), customer.contact],
    [t("pages.customers.note"), customer.note],
  ].filter(([, value]) => value !== "");
  if (facts.length === 0) {
    return <p className={styles.note}>{t("pages.customers.noFacts")}</p>;
  }
  return (
    <dl className={styles.facts}>
      {facts.map(([label, value]) => (
        <div key={label} className={styles.fact}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The accounts, one line each. */
function Accounts({ customer, open, onOpen }: OpenProps) {
  const { t } = useTranslation();
  if (customer.accounts.length === 0) {
    return <p className={styles.note}>{t("pages.customers.noAccounts")}</p>;
  }
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">{t("pages.customers.phone")}</th>
          <th scope="col">{t("pages.customers.label")}</th>
          <th scope="col">
            <span className="visually-hidden">{t("pages.customers.edit")}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {customer.accounts.map((account) => (
          <tr key={account.id}>
            <td className={styles.phone}>{account.phone ?? t("pages.customers.noLogin")}</td>
            <td className={styles.label}>{account.label}</td>
            <td className={styles.end}>
              <Button
                className={styles.small}
                aria-pressed={open?.form === "account" && open.id === account.id}
                onClick={() => onOpen({ form: "account", id: account.id })}
              >
                {t("pages.customers.edit")}
              </Button>
              <Button
                className={styles.small}
                onClick={() => onOpen({ form: "removeAccount", id: account.id })}
              >
                {t("pages.customers.remove")}
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** What a machine loses with an account it books with. */
function useInUse() {
  const { t } = useTranslation();
  const machines = useMachines();
  return (accounts: readonly CustomerAccount[]): string[] =>
    accounts.flatMap(({ device, phone }) =>
      device === null
        ? []
        : t("pages.customers.inUse", {
            machine: machineName(t, machines, device),
            phone: phone ?? "",
          }),
    );
}

function RemoveCustomer({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { t } = useTranslation();
  const inUse = useInUse();
  const remove = useRemoveCustomer();
  const count = customer.accounts.length;
  return (
    <RemoveQuestion
      title={t("pages.customers.removeAsk", { name: customer.name })}
      lost={[
        ...(count > 0 ? [t("pages.customers.lostAccounts", { count })] : []),
        ...inUse(customer.accounts),
      ]}
      pending={remove.isPending}
      error={remove.error}
      onRemove={() => remove.mutate(customer.id)}
      onClose={onClose}
    />
  );
}

function RemoveAccount({ account, onClose }: { account: CustomerAccount; onClose: () => void }) {
  const { t } = useTranslation();
  const inUse = useInUse();
  const remove = useRemoveAccount();
  return (
    <RemoveQuestion
      title={t("pages.customers.removeAsk", {
        name: [account.phone, account.label].filter(Boolean).join(" · "),
      })}
      lost={[t("pages.customers.lostAccount"), ...inUse([account])]}
      pending={remove.isPending}
      error={remove.error}
      onRemove={() => remove.mutate(account.id, { onSuccess: onClose })}
      onClose={onClose}
    />
  );
}

interface OpenProps {
  customer: Customer;
  open: Open | null;
  onOpen: (open: Open | null) => void;
}

/** A customer: who they are, then the Vinhomes accounts they gave. One form is open at a time. */
export function CustomerDetail({ customer }: { customer: Customer }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState<Open | null>(null);
  const close = () => setOpen(null);
  const edited = open?.form === "account" ? open : null;
  const editedAccount = customer.accounts.find((account) => account.id === edited?.id) ?? null;
  const removed = customer.accounts.find(
    (account) => open?.form === "removeAccount" && account.id === open.id,
  );
  return (
    <section aria-label={customer.name} className={styles.body}>
      {open?.form === "customer" ? (
        <CustomerForm customer={customer} onClose={close} />
      ) : (
        <>
          <div className={styles.head}>
            <h2 className={styles.name}>{customer.name}</h2>
            <div className={styles.buttons}>
              <Button className={styles.small} onClick={() => setOpen({ form: "customer" })}>
                {t("pages.customers.editCustomer")}
              </Button>
              <Button className={styles.small} onClick={() => setOpen({ form: "removeCustomer" })}>
                {t("pages.customers.removeCustomer")}
              </Button>
            </div>
          </div>
          {open?.form === "removeCustomer" && (
            <RemoveCustomer customer={customer} onClose={close} />
          )}
          <Facts customer={customer} />
        </>
      )}
      <div className={styles.head}>
        <h3 className={styles.section}>{t("pages.customers.accounts")}</h3>
        <Button className={styles.small} onClick={() => setOpen({ form: "account", id: null })}>
          {t("pages.customers.addAccount")}
        </Button>
      </div>
      <Accounts customer={customer} open={open} onOpen={setOpen} />
      {removed !== undefined && (
        <RemoveAccount key={removed.id} account={removed} onClose={close} />
      )}
      {edited !== null && (edited.id === null || editedAccount !== null) && (
        <AccountForm
          key={edited.id ?? "new"}
          customerId={customer.id}
          account={editedAccount}
          onClose={close}
        />
      )}
    </section>
  );
}
