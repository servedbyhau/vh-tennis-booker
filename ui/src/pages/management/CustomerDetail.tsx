import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Customer } from "../../api/types";
import { Button } from "../../components/Button";
import styles from "./CustomerDetail.module.css";
import { AccountForm, CustomerForm } from "./CustomerForms";

/** The one form open: the customer's, or an account's, a new one without `id`. */
type Open = { form: "customer" } | { form: "account"; id: string | null };

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
            </td>
          </tr>
        ))}
      </tbody>
    </table>
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
