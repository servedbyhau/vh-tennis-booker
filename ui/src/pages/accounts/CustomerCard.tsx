import { useTranslation } from "react-i18next";
import type { Customer, CustomerAccount } from "../../api/types";
import { Button } from "../../components/Button";
import { useMachines } from "../../machines";
import { machineName } from "../home/ticketText";
import styles from "./CustomerCard.module.css";
import { AccountForm, CustomerForm } from "./CustomerForms";
import type { Open } from "./open";

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
    <div role="group" aria-label={t("pages.accounts.attachOf", { phone })} className={styles.chips}>
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

interface CustomerCardProps extends Omit<MachineChipsProps, "account"> {
  customer: Customer;
  open: Open | null;
  onOpen: (open: Open | null) => void;
}

/** A customer: who they are, then one line per account with the machine it is attached to. */
export function CustomerCard({ customer, open, onOpen, ...chips }: CustomerCardProps) {
  const { t } = useTranslation();
  const close = () => onOpen(null);
  const edited = open?.form === "account" && open.customerId === customer.id ? open : null;
  const editedAccount = customer.accounts.find((account) => account.id === edited?.id) ?? null;
  return (
    <section aria-label={customer.name} className={styles.card}>
      {open?.form === "customer" && open.id === customer.id ? (
        <CustomerForm customer={customer} onClose={close} />
      ) : (
        <div className={styles.head}>
          <div className={styles.who}>
            <h3 className={styles.name}>{customer.name}</h3>
            {customer.note !== "" && <p className={styles.note}>{customer.note}</p>}
          </div>
          <Button
            className={styles.small}
            onClick={() => onOpen({ form: "customer", id: customer.id })}
          >
            {t("pages.accounts.editCustomer")}
          </Button>
          <Button
            className={styles.small}
            onClick={() => onOpen({ form: "account", customerId: customer.id, id: null })}
          >
            {t("pages.accounts.addAccount")}
          </Button>
        </div>
      )}
      {customer.accounts.length === 0 ? (
        <p className={styles.note}>{t("pages.accounts.noAccounts")}</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{t("pages.accounts.phone")}</th>
              <th scope="col">{t("pages.accounts.label")}</th>
              <th scope="col">{t("pages.accounts.attach")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("pages.accounts.edit")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {customer.accounts.map((account) => (
              <tr
                key={account.id}
                className={account.device === null ? undefined : styles.attached}
              >
                <td className={styles.phone}>{account.phone ?? t("pages.accounts.noLogin")}</td>
                <td className={styles.label}>{account.label}</td>
                <td>
                  <MachineChips account={account} {...chips} />
                </td>
                <td className={styles.end}>
                  <Button
                    className={styles.small}
                    onClick={() =>
                      onOpen({ form: "account", customerId: customer.id, id: account.id })
                    }
                  >
                    {t("pages.accounts.edit")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
