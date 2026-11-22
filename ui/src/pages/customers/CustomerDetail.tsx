import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useAttachAccount, useDetachAccount } from "../../api/mutations";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { useMachines } from "../../machines";
import { machineName } from "../home/ticketText";
import styles from "./CustomerDetail.module.css";
import { AccountForm, CustomerForm } from "./CustomerForms";

/** The one form open: the customer's, or an account's, a new one without `id`. */
type Open = { form: "customer" } | { form: "account"; id: string | null };

interface MachineChipsProps {
  account: CustomerAccount;
  disabled: boolean;
  onAttach: (accountId: string, mumuIndex: number) => void;
  onDetach: (mumuIndex: number) => void;
}

/** The machines as buttons: the pressed one books with the account; a press again frees it. */
function MachineChips({ account, disabled, onAttach, onDetach }: MachineChipsProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  const phone = account.phone ?? "";
  const listed = machines.flatMap((machine) => machine.mumuIndex ?? []);
  // One attached to a machine that has no tab any more is still freed here.
  const other = account.device !== null && !listed.includes(account.device) ? [account.device] : [];
  return (
    <div
      role="group"
      aria-label={t("pages.customers.attachOf", { phone })}
      className={styles.chips}
    >
      {[...listed, ...other].map((index) => {
        const attached = account.device === index;
        return (
          <button
            key={index}
            type="button"
            aria-pressed={attached}
            disabled={disabled || (account.phone === null && !attached)}
            className={styles.chip}
            onClick={() => (attached ? onDetach(index) : onAttach(account.id, index))}
          >
            {machineName(t, machines, index)}
          </button>
        );
      })}
    </div>
  );
}

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

/** The accounts, one line each, with the machine each one is attached to. */
function Accounts({ customer, open, onOpen }: OpenProps) {
  const { t } = useTranslation();
  const attach = useAttachAccount();
  const detach = useDetachAccount();
  const error = attach.error ?? detach.error;
  const pending = attach.isPending || detach.isPending;

  function onAttach(accountId: string, mumuIndex: number) {
    detach.reset();
    attach.mutate({ mumuIndex, accountId });
  }

  function onDetach(mumuIndex: number) {
    attach.reset();
    detach.mutate(mumuIndex);
  }

  if (customer.accounts.length === 0) {
    return <p className={styles.note}>{t("pages.customers.noAccounts")}</p>;
  }
  return (
    <>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{t("pages.customers.phone")}</th>
            <th scope="col">{t("pages.customers.label")}</th>
            <th scope="col">{t("pages.customers.attach")}</th>
            <th scope="col">
              <span className="visually-hidden">{t("pages.customers.edit")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {customer.accounts.map((account) => (
            <tr key={account.id} className={account.device === null ? undefined : styles.attached}>
              <td className={styles.phone}>{account.phone ?? t("pages.customers.noLogin")}</td>
              <td className={styles.label}>{account.label}</td>
              <td>
                <MachineChips
                  account={account}
                  disabled={pending}
                  onAttach={onAttach}
                  onDetach={onDetach}
                />
              </td>
              <td className={styles.end}>
                <Button
                  className={styles.small}
                  aria-pressed={open?.form === "account" && open.id === account.id}
                  onClick={() => onOpen({ form: "account", id: account.id })}
                >
                  {t("pages.customers.edit")}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error === null ? (
        <p className={styles.note}>
          {t("pages.customers.machines.hint", { dryRun: t("pages.ticket.dryRun.button") })}
        </p>
      ) : (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      )}
    </>
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
  return (
    <section aria-label={customer.name} className={styles.body}>
      {open?.form === "customer" ? (
        <CustomerForm customer={customer} onClose={close} />
      ) : (
        <>
          <div className={styles.head}>
            <h2 className={styles.name}>{customer.name}</h2>
            <Button className={styles.small} onClick={() => setOpen({ form: "customer" })}>
              {t("pages.customers.editCustomer")}
            </Button>
          </div>
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
