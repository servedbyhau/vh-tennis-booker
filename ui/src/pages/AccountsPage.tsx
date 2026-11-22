import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../api/errors";
import { useAttachAccount, useDetachAccount } from "../api/mutations";
import { useCustomers } from "../api/queries";
import { Button } from "../components/Button";
import { PageTitle } from "../components/PageTitle";
import { QueryView } from "../components/QueryView";
import { EmptyState } from "../components/States";
import styles from "./AccountsPage.module.css";
import { CustomerCard } from "./accounts/CustomerCard";
import { CustomerForm } from "./accounts/CustomerForms";
import { MachineCards } from "./accounts/MachineCards";
import type { Open } from "./accounts/open";

/**
 * The accounts, apart from the booking: which account each machine books with, then the
 * customers with the Vinhomes accounts they gave. A press on a machine of an account's line
 * attaches it there; the next run logs the machine's app in with it.
 */
export function AccountsPage() {
  const { t } = useTranslation();
  const customers = useCustomers();
  const attach = useAttachAccount();
  const detach = useDetachAccount();
  const [open, setOpen] = useState<Open | null>(null);
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

  return (
    <div className={styles.page}>
      <PageTitle>{t("pages.accounts.title")}</PageTitle>
      <div className={styles.intro}>
        <h1 className={styles.title}>{t("pages.accounts.title")}</h1>
        <p className={styles.lead}>{t("pages.accounts.lead")}</p>
      </div>
      <QueryView query={customers}>
        {(list) => (
          <>
            <section aria-labelledby="machines-title" className={styles.section}>
              <h2 id="machines-title" className={styles.heading}>
                {t("pages.accounts.machines.title")}
              </h2>
              <MachineCards customers={list} disabled={pending} onDetach={onDetach} />
              {error === null ? (
                <p className={styles.hint}>
                  {t("pages.accounts.machines.hint", { dryRun: t("pages.ticket.dryRun.button") })}
                </p>
              ) : (
                <p role="alert" className={styles.error}>
                  {errorMessage(t, error)}
                </p>
              )}
            </section>
            <section aria-labelledby="customers-title" className={styles.section}>
              <div className={styles.row}>
                <h2 id="customers-title" className={styles.heading}>
                  {t("pages.accounts.customers")}
                </h2>
                <Button variant="primary" onClick={() => setOpen({ form: "customer", id: null })}>
                  {t("pages.accounts.add")}
                </Button>
              </div>
              {open?.form === "customer" && open.id === null && (
                <div className={styles.card}>
                  <CustomerForm customer={null} onClose={() => setOpen(null)} />
                </div>
              )}
              {list.length === 0 && <EmptyState>{t("pages.accounts.empty")}</EmptyState>}
              {list.map((customer) => (
                <CustomerCard
                  key={customer.id}
                  customer={customer}
                  open={open}
                  disabled={pending}
                  onOpen={setOpen}
                  onAttach={onAttach}
                  onDetach={onDetach}
                />
              ))}
            </section>
          </>
        )}
      </QueryView>
    </div>
  );
}
