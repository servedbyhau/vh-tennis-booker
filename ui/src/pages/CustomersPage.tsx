import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { useCustomers } from "../api/queries";
import type { Customer } from "../api/types";
import { PageTitle } from "../components/PageTitle";
import { QueryView } from "../components/QueryView";
import { EmptyState } from "../components/States";
import styles from "./CustomersPage.module.css";
import { CustomerDetail } from "./customers/CustomerDetail";
import { CustomerForm } from "./customers/CustomerForms";
import { CustomerList } from "./customers/CustomerList";

interface ColumnsProps {
  customers: readonly Customer[];
  /** The customer in the address, shown first while there is none. */
  chosen: string | null;
  onChoose: (id: string) => void;
}

function Columns({ customers, chosen, onChoose }: ColumnsProps) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const shown = customers.find((customer) => customer.id === chosen) ?? customers[0];

  function choose(id: string) {
    setAdding(false);
    onChoose(id);
  }

  return (
    <div className={styles.columns}>
      <CustomerList
        customers={customers}
        shown={adding ? null : (shown?.id ?? null)}
        onChoose={choose}
        onAdd={() => setAdding(true)}
      />
      <div className={styles.detail}>
        {adding ? (
          <div className={styles.form}>
            <h2 className={styles.title}>{t("pages.customers.add")}</h2>
            <CustomerForm
              customer={null}
              onClose={() => setAdding(false)}
              onSaved={(customer) => choose(customer.id)}
            />
          </div>
        ) : shown === undefined ? (
          <div className={styles.form}>
            <EmptyState>{t("pages.customers.empty")}</EmptyState>
          </div>
        ) : (
          // Another customer starts with no form open.
          <CustomerDetail key={shown.id} customer={shown} />
        )}
      </div>
    </div>
  );
}

/**
 * The management page, for now the customers: the list on the left, and on the right the one
 * chosen: who they are and the Vinhomes accounts they gave. The address keeps the choice.
 */
export function CustomersPage() {
  const { t } = useTranslation();
  const customers = useCustomers();
  const [params, setParams] = useSearchParams();
  return (
    <>
      <PageTitle>{t("nav.management")}</PageTitle>
      <h1 className="visually-hidden">{t("nav.management")}</h1>
      <QueryView query={customers}>
        {(list) => (
          <Columns
            customers={list}
            chosen={params.get("customer")}
            onChoose={(id) => setParams({ customer: id }, { replace: true })}
          />
        )}
      </QueryView>
    </>
  );
}
