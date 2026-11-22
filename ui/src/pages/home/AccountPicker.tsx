import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useAttachAccount, useDetachAccount } from "../../api/mutations";
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount } from "../../api/types";
import { QueryView } from "../../components/QueryView";
import { useMachines } from "../../machines";
import styles from "./SetupTab.module.css";
import { machineName } from "./ticketText";

/** The account attached to the machine, with its customer. */
function attachedTo(customers: readonly Customer[], mumuIndex: number) {
  for (const customer of customers) {
    const account = customer.accounts.find((item) => item.device === mumuIndex);
    if (account !== undefined) {
      return { customer, account };
    }
  }
  return null;
}

interface PickerProps {
  customers: readonly Customer[];
  mumuIndex: number;
}

/** The two choices, the customer and one of their accounts; picking an account saves it. */
function Picker({ customers, mumuIndex }: PickerProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  const attach = useAttachAccount();
  const detach = useDetachAccount();
  const attached = attachedTo(customers, mumuIndex);
  /** The customer chosen while no account of theirs is picked yet. */
  const [chosen, setChosen] = useState<string | null>(null);
  const customer = customers.find((item) => item.id === chosen) ?? attached?.customer ?? null;
  const account = attached?.customer.id === customer?.id ? attached?.account : undefined;
  const error = attach.error ?? detach.error;
  const pending = attach.isPending || detach.isPending;

  function pickCustomer(id: string) {
    attach.reset();
    detach.reset();
    if (id === "") {
      setChosen(null);
      if (attached !== null) {
        detach.mutate(mumuIndex);
      }
    } else {
      setChosen(id);
    }
  }

  function pickAccount(id: string) {
    detach.reset();
    attach.mutate({ mumuIndex, accountId: id }, { onSuccess: () => setChosen(null) });
  }

  /** What an account is listed as; one on another machine says where, and is not picked. */
  function accountText(item: CustomerAccount): string {
    const parts = [item.phone ?? t("pages.customers.noLogin"), item.label];
    if (item.device !== null && item.device !== mumuIndex) {
      const machine = machineName(t, machines, item.device);
      parts.push(t("pages.setup.login.onMachine", { machine }));
    }
    return parts.filter((part) => part !== "").join(" · ");
  }

  return (
    <div className={styles.form}>
      <label className={styles.field}>
        <span className={styles.label}>{t("pages.setup.login.customer")}</span>
        <select
          value={customer?.id ?? ""}
          disabled={pending}
          onChange={(event) => pickCustomer(event.target.value)}
        >
          <option value="">{t("pages.setup.login.none")}</option>
          {customers.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {customer !== null && (
        <label className={styles.field}>
          <span className={styles.label}>{t("pages.setup.login.account")}</span>
          <select
            value={account?.id ?? ""}
            disabled={pending}
            onChange={(event) => pickAccount(event.target.value)}
          >
            <option value="" disabled>
              {t("pages.setup.login.pick")}
            </option>
            {customer.accounts.map((item) => (
              <option
                key={item.id}
                value={item.id}
                disabled={
                  item.phone === null || (item.device !== null && item.device !== mumuIndex)
                }
              >
                {accountText(item)}
              </option>
            ))}
          </select>
        </label>
      )}
      {error !== null ? (
        <p role="alert" className={styles.error}>
          {errorMessage(t, error)}
        </p>
      ) : (
        <p role="status" className={styles.note}>
          {account !== undefined
            ? t("pages.setup.login.attached", { dryRun: t("pages.ticket.dryRun.button") })
            : t(attached === null ? "pages.setup.login.free" : "pages.setup.login.notYet")}
        </p>
      )}
    </div>
  );
}

/**
 * The customer's account a machine books with: each run checks that the machine's Vinhomes app
 * is logged in with it, and changes it if not.
 */
export function AccountPicker({ mumuIndex }: { mumuIndex: number }) {
  const { t } = useTranslation();
  const id = useId();
  const customers = useCustomers();
  return (
    <section aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`} className={styles.heading}>
        {t("pages.setup.login.title")}
      </h3>
      <p className={styles.note}>{t("pages.setup.login.why")}</p>
      <QueryView
        query={customers}
        isEmpty={(list) => list.length === 0}
        empty={t("pages.setup.login.noCustomers")}
      >
        {(list) => <Picker customers={list} mumuIndex={mumuIndex} />}
      </QueryView>
    </section>
  );
}
