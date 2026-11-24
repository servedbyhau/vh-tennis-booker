import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRemoveAccount, useRemoveCustomer } from "../../api/mutations";
import type { Customer, CustomerAccount } from "../../api/types";
import { Icon, type IconName } from "../../components/Icon";
import { IconButton } from "../../components/IconButton";
import styles from "./CustomerDetail.module.css";
import { AccountForm, CustomerForm } from "./CustomerForms";
import { accountFound } from "./customerSearch";
import { RemoveQuestion } from "./RemoveQuestion";

/** What is open: the customer's form, an account's (a new one without `id`), or a removal. */
type Open =
  | { form: "customer" }
  | { form: "account"; id: string | null }
  | { form: "removeCustomer" }
  | { form: "removeAccount"; id: string };

/** Who the customer is, a line each behind its icon; what is not known is left out. */
function Facts({ customer }: { customer: Customer }) {
  const { t } = useTranslation();
  const facts: { icon: IconName; label: string; value: string }[] = [
    { icon: "person", label: t("pages.customers.representative"), value: customer.representative },
    { icon: "phone", label: t("pages.customers.contact"), value: customer.contact },
    { icon: "note", label: t("pages.customers.note"), value: customer.note },
  ];
  const known = facts.filter(({ value }) => value !== "");
  if (known.length === 0) {
    return <p className={styles.none}>{t("pages.customers.noFacts")}</p>;
  }
  return (
    <dl className={styles.facts}>
      {known.map(({ icon, label, value }) => (
        <div key={icon} className={styles.fact} title={label}>
          <dt>
            <Icon name={icon} />
            <span className="visually-hidden">{label}</span>
          </dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RemoveCustomer({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { t } = useTranslation();
  const remove = useRemoveCustomer();
  return (
    <RemoveQuestion
      title={t("pages.customers.removeAsk", { name: customer.name })}
      accounts={customer.accounts}
      pending={remove.isPending}
      error={remove.error}
      onRemove={() => remove.mutate(customer.id)}
      onClose={onClose}
    />
  );
}

function RemoveAccount({ account, onClose }: { account: CustomerAccount; onClose: () => void }) {
  const { t } = useTranslation();
  const remove = useRemoveAccount();
  const name = [account.phone, account.label].filter(Boolean).join(" · ");
  return (
    <RemoveQuestion
      title={t("pages.customers.removeAsk", { name })}
      accounts={[account]}
      named
      pending={remove.isPending}
      error={remove.error}
      onRemove={() => remove.mutate(account.id, { onSuccess: onClose })}
      onClose={onClose}
    />
  );
}

/** How long "copied" shows after the phone number is copied. */
const COPIED_MS = 2000;

/** Copy `phone` to paste it elsewhere; return what to say of it until it fades. */
function useCopy(phone: string | null) {
  const [said, setSaid] = useState<"copied" | "failed" | null>(null);
  useEffect(() => {
    if (said === null) {
      return;
    }
    const timer = setTimeout(() => setSaid(null), COPIED_MS);
    return () => clearTimeout(timer);
  }, [said]);
  const copy = () => {
    if (phone !== null) {
      void navigator.clipboard.writeText(phone).then(
        () => setSaid("copied"),
        () => setSaid("failed"),
      );
    }
  };
  return { said, copy };
}

interface AccountRowProps {
  customerId: string;
  account: CustomerAccount;
  /** Whether the search found this account by its name or phone number. */
  found: boolean;
  open: Open | null;
  onOpen: (open: Open | null) => void;
}

/** An account: its phone and label, its form under it, or the question before its removal. */
function AccountRow({ customerId, account, found, open, onOpen }: AccountRowProps) {
  const { t } = useTranslation();
  const close = () => onOpen(null);
  const edited = open?.form === "account" && open.id === account.id;
  const removed = open?.form === "removeAccount" && open.id === account.id;
  const { said, copy } = useCopy(account.phone);
  return (
    <li className={styles.account}>
      <div className={`${styles.row} ${found ? styles.found : ""}`}>
        <span className={styles.mark}>
          <Icon name="key" />
        </span>
        <span className={styles.login}>
          <span className={styles.phone}>{account.phone ?? t("pages.customers.noLogin")}</span>
          {account.label !== "" && <span className={styles.label}>{account.label}</span>}
        </span>
        {said !== null && (
          <span role="status" className={styles.label}>
            {t(said === "copied" ? "pages.customers.copied" : "pages.customers.copyFailed")}
          </span>
        )}
        {account.phone !== null && (
          <IconButton icon="copy" label={t("pages.customers.copyPhone")} onClick={copy} />
        )}
        <IconButton
          icon="edit"
          label={t("pages.customers.edit")}
          aria-expanded={edited}
          onClick={() => onOpen(edited ? null : { form: "account", id: account.id })}
        />
        <IconButton
          icon="remove"
          variant="danger"
          label={t("pages.customers.remove")}
          aria-expanded={removed}
          onClick={() => onOpen(removed ? null : { form: "removeAccount", id: account.id })}
        />
      </div>
      {edited && <AccountForm customerId={customerId} account={account} onClose={close} />}
      {removed && <RemoveAccount account={account} onClose={close} />}
    </li>
  );
}

/**
 * A customer: who they are, then the Vinhomes accounts they gave, those the search found by
 * their name or number marked. One form is open at a time.
 */
export function CustomerDetail({ customer, query }: { customer: Customer; query: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState<Open | null>(null);
  const close = () => setOpen(null);
  const adding = open?.form === "account" && open.id === null;
  const removing = open?.form === "removeCustomer";
  return (
    <section aria-label={customer.name} className={styles.body}>
      {open?.form === "customer" ? (
        <CustomerForm customer={customer} onClose={close} />
      ) : (
        <>
          <div className={styles.head}>
            <h2 className={styles.name}>{customer.name}</h2>
            <IconButton
              icon="edit"
              label={t("pages.customers.editCustomer")}
              onClick={() => setOpen({ form: "customer" })}
            />
            <IconButton
              icon="remove"
              variant="danger"
              label={t("pages.customers.removeCustomer")}
              aria-expanded={removing}
              onClick={() => setOpen(removing ? null : { form: "removeCustomer" })}
            />
          </div>
          {removing && <RemoveCustomer customer={customer} onClose={close} />}
          <Facts customer={customer} />
        </>
      )}
      <div className={`${styles.head} ${styles.accountsHead}`}>
        <h3 className={styles.section}>{t("pages.customers.accounts")}</h3>
        <IconButton
          icon="add"
          label={t("pages.customers.addAccount")}
          aria-expanded={adding}
          onClick={() => setOpen(adding ? null : { form: "account", id: null })}
        />
      </div>
      {adding && <AccountForm customerId={customer.id} account={null} onClose={close} />}
      {customer.accounts.length > 0 ? (
        <ul aria-label={t("pages.customers.accounts")} className={styles.accounts}>
          {customer.accounts.map((account) => (
            <AccountRow
              key={account.id}
              customerId={customer.id}
              account={account}
              found={accountFound(account, query)}
              open={open}
              onOpen={setOpen}
            />
          ))}
        </ul>
      ) : (
        !adding && <p className={styles.none}>{t("pages.customers.noAccounts")}</p>
      )}
    </section>
  );
}
