import { useTranslation } from "react-i18next";
import type { Customer } from "../../api/types";
import { Icon } from "../../components/Icon";
import { IconButton } from "../../components/IconButton";
import styles from "./CustomerList.module.css";

interface CustomerListProps {
  /** The customers the search keeps. */
  customers: readonly Customer[];
  /** The customer shown beside the list, `null` while one is added. */
  shown: string | null;
  onChoose: (id: string) => void;
  onAdd: () => void;
  query: string;
  onQuery: (query: string) => void;
}

/** How many accounts a customer gave: a key and the number, in words for screen readers. */
function AccountCount({ count }: { count: number }) {
  const { t } = useTranslation();
  const words = t("pages.customers.accountCount", { count });
  return (
    <span className={styles.count} title={words}>
      <Icon name="key" />
      <span aria-hidden="true">{count}</span>
      <span className="visually-hidden">{words}</span>
    </span>
  );
}

/**
 * The customers, with who speaks for them and how many accounts they gave, under a search by
 * their name and facts or an account's name or phone number.
 */
export function CustomerList({
  customers,
  shown,
  onChoose,
  onAdd,
  query,
  onQuery,
}: CustomerListProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <h2 id="customers-title" className={styles.title}>
          {t("pages.customers.title")}
        </h2>
        <IconButton icon="add" variant="solid" label={t("pages.customers.add")} onClick={onAdd} />
      </div>
      <label className={styles.search}>
        <Icon name="search" />
        <input
          type="search"
          aria-label={t("pages.customers.search")}
          placeholder={t("pages.customers.search")}
          value={query}
          onChange={(event) => onQuery(event.target.value)}
        />
      </label>
      <nav aria-labelledby="customers-title" className={styles.scroll}>
        {customers.length === 0 && query.trim() !== "" && (
          <p className={styles.none}>{t("pages.customers.noMatch")}</p>
        )}
        <ul className={styles.list}>
          {customers.map((customer) => (
            <li key={customer.id}>
              <button
                type="button"
                aria-current={customer.id === shown}
                className={styles.customer}
                onClick={() => onChoose(customer.id)}
              >
                <span className={styles.avatar}>
                  <Icon name="person" />
                </span>
                <span className={styles.who}>
                  <span className={styles.name}>{customer.name}</span>
                  {customer.representative !== "" && (
                    <span className={styles.sub}>{customer.representative}</span>
                  )}
                </span>
                <AccountCount count={customer.accounts.length} />
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
