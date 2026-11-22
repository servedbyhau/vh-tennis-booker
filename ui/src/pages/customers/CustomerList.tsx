import { useTranslation } from "react-i18next";
import type { Customer } from "../../api/types";
import { Button } from "../../components/Button";
import { accountOn, useMachines } from "../../machines";
import { machineName } from "../home/ticketText";
import styles from "./CustomerList.module.css";

/** The machines that book for a customer. */
function devicesOf(customer: Customer): number[] {
  return customer.accounts.flatMap((account) => account.device ?? []).sort((a, b) => a - b);
}

/** Who each machine books for; a press shows that customer. */
function MachineRows({ customers, onChoose }: Pick<CustomerListProps, "customers" | "onChoose">) {
  const { t } = useTranslation();
  const machines = useMachines();
  return (
    <section aria-labelledby="machines-title" className={styles.machines}>
      <h2 id="machines-title" className={styles.heading}>
        {t("pages.customers.machines.title")}
      </h2>
      <ul className={styles.rows}>
        {machines.map((machine) => {
          const found = machine.mumuIndex === null ? null : accountOn(customers, machine.mumuIndex);
          const name = t("pages.ticket.instanceName", { number: machine.place + 1 });
          const label = machine.enabled
            ? name
            : t("pages.customers.machines.off", { machine: name });
          return (
            <li key={machine.key} className={styles.machine}>
              <span className={styles.machineName}>{label}</span>
              {found === null ? (
                <span className={styles.none}>{t("pages.customers.machines.none")}</span>
              ) : (
                <button
                  type="button"
                  className={styles.link}
                  onClick={() => onChoose(found.customer.id)}
                >
                  {found.customer.name}
                  <span className={styles.phone}>{found.account.phone}</span>
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

interface CustomerListProps {
  customers: readonly Customer[];
  /** The customer shown beside the list, `null` while one is added. */
  shown: string | null;
  onChoose: (id: string) => void;
  onAdd: () => void;
}

/** Every customer with the machine that books for them, and the machines under them. */
export function CustomerList({ customers, shown, onChoose, onAdd }: CustomerListProps) {
  const { t } = useTranslation();
  const machines = useMachines();
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
                    {customer.representative ||
                      t("pages.customers.accountCount", { count: customer.accounts.length })}
                  </span>
                </span>
                {devicesOf(customer).map((device) => (
                  <span key={device} className={styles.badge}>
                    {machineName(t, machines, device)}
                  </span>
                ))}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <MachineRows customers={customers} onChoose={onChoose} />
    </div>
  );
}
