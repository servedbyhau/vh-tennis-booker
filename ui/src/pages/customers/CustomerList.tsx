import { useTranslation } from "react-i18next";
import type { Customer } from "../../api/types";
import { Button } from "../../components/Button";
import styles from "./CustomerList.module.css";

interface CustomerListProps {
  customers: readonly Customer[];
  /** The customer shown beside the list, `null` while one is added. */
  shown: string | null;
  onChoose: (id: string) => void;
  onAdd: () => void;
}

/** Every customer, with who speaks for them and how many accounts they gave. */
export function CustomerList({ customers, shown, onChoose, onAdd }: CustomerListProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <h2 id="customers-title" className={styles.title}>
          {t("pages.customers.title")}
        </h2>
        <Button variant="primary" className={styles.add} onClick={onAdd}>
          {t("pages.customers.add")}
        </Button>
      </div>
      <nav aria-labelledby="customers-title" className={styles.scroll}>
        <ul className={styles.list}>
          {customers.map((customer) => (
            <li key={customer.id}>
              <button
                type="button"
                aria-current={customer.id === shown}
                className={styles.customer}
                onClick={() => onChoose(customer.id)}
              >
                <span className={styles.who}>
                  <span className={styles.name}>{customer.name}</span>
                  <span className={styles.sub}>
                    {[
                      customer.representative,
                      t("pages.customers.accountCount", { count: customer.accounts.length }),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
