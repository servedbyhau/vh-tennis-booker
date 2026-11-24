import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount, QuotaReading } from "../../api/types";
import { Icon } from "../../components/Icon";
import { IconButton } from "../../components/IconButton";
import { PageTitle } from "../../components/PageTitle";
import { QueryView } from "../../components/QueryView";
import { EmptyState } from "../../components/States";
import { leftOf, sportName, useBookingMonth } from "../../quota";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";
import { useQuotaRefresh } from "./quotaRefresh";

/** Fewer bookings left than this is marked, to look at before it runs out. */
const FEW_LEFT = 3;

/** A sport's column: its key, the sport when known, else the app's words of its utility. */
interface Column {
  key: string;
  sport: string | null;
  utility: string;
}

/** Return the months the readings hold, the earliest first. */
function monthsOf(customers: readonly Customer[]): string[] {
  const months = customers.flatMap((customer) =>
    customer.accounts.flatMap((account) => account.quota.map((reading) => reading.month)),
  );
  return [...new Set(months)].sort();
}

/** Return the sports read in `month`, each once, in the order first met. */
function columnsOf(customers: readonly Customer[], month: string): Column[] {
  const found = new Map<string, Column>();
  for (const customer of customers) {
    for (const account of customer.accounts) {
      for (const reading of account.quota) {
        const key = reading.sport ?? reading.utility;
        if (reading.month === month && !found.has(key)) {
          found.set(key, { key, sport: reading.sport ?? null, utility: reading.utility });
        }
      }
    }
  }
  return [...found.values()];
}

/** One cell: what is left of a sport, marked when little or none is; empty when never read. */
function Left({ reading }: { reading: QuotaReading | undefined }) {
  const { t } = useTranslation();
  const f = useFormat();
  if (reading === undefined) {
    return <span className={styles.muted}>–</span>;
  }
  const left = leftOf(reading);
  const tone = left === 0 ? styles.bad : left < FEW_LEFT ? styles.warn : styles.good;
  return (
    <span
      className={`${styles.chip} ${tone}`}
      title={t("pages.quota.readAt", {
        time: f.time(reading.read_at),
        day: f.shortDate(reading.read_at),
      })}
    >
      {t("pages.quota.left", { left, limit: reading.month_limit })}
    </span>
  );
}

interface RowProps {
  customer: Customer;
  account: CustomerAccount;
  columns: Column[];
  month: string;
}

/** One account in a row: whose it is, its machine, what is left of each sport, and a read again. */
function Row({ customer, account, columns, month }: RowProps) {
  const { t } = useTranslation();
  const refresh = useQuotaRefresh(account.device);
  const name = [customer.name, account.label].filter(Boolean).join(" · ");
  return (
    <tr>
      <td>
        {name}
        <br />
        <span className={`${styles.muted} ${styles.mono}`}>{account.phone ?? ""}</span>
      </td>
      <td>
        {account.device === null ? (
          <span className={styles.muted}>–</span>
        ) : (
          t("pages.quota.machine", { index: account.device })
        )}
      </td>
      {columns.map((column) => (
        <td key={column.key}>
          <Left
            reading={account.quota.find(
              (reading) =>
                reading.month === month && (reading.sport ?? reading.utility) === column.key,
            )}
          />
        </td>
      ))}
      <td>
        {account.device !== null && (
          <IconButton
            icon="refresh"
            label={t("quota.refresh.button")}
            disabled={refresh.running}
            onClick={refresh.read}
          />
        )}
        {refresh.text !== null && (
          <span role="status" className={styles.muted}>
            {refresh.text}
          </span>
        )}
      </td>
    </tr>
  );
}

/** The table of every account and sport in one month, with the months to choose from. */
function Table({ customers }: { customers: Customer[] }) {
  const { t } = useTranslation();
  const booking = useBookingMonth();
  const months = monthsOf(customers);
  const [chosen, setChosen] = useState<string | null>(null);
  const month = chosen ?? booking ?? months[0];
  const accounts = customers.flatMap((customer) =>
    customer.accounts.map((account) => ({ customer, account })),
  );
  if (month === undefined || accounts.length === 0) {
    return <EmptyState>{t("pages.quota.empty")}</EmptyState>;
  }
  const columns = columnsOf(customers, month);
  return (
    <section aria-label={t("pages.quota.title")} className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={`${styles.sectionTitle} ${styles.value}`}>
          {t("pages.quota.month", { month: `${month.slice(5)}/${month.slice(0, 4)}` })}
        </h2>
        {months.length > 1 && (
          <span role="group" aria-label={t("pages.quota.months")} className={styles.chips}>
            {months.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={item === month}
                className={`${styles.chip} ${item === month ? styles.good : ""}`}
                onClick={() => setChosen(item)}
              >
                {`${item.slice(5)}/${item.slice(0, 4)}`}
              </button>
            ))}
          </span>
        )}
      </div>
      <p className={styles.muted}>
        <Icon name="alarm" /> {t("pages.quota.hint")}
      </p>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{t("pages.quota.account")}</th>
            <th>{t("pages.quota.onMachine")}</th>
            {columns.map((column) => (
              <th key={column.key}>{sportName(t, column.sport, column.utility)}</th>
            ))}
            <th>
              <span className="visually-hidden">{t("quota.refresh.button")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {accounts.map(({ customer, account }) => (
            <Row
              key={account.id}
              customer={customer}
              account={account}
              columns={columns}
              month={month}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

/**
 * What every account has left of each sport's quota in a month, as the runs and the reads asked
 * for last saw it, in one table: a row an account, a column a sport, little left marked.
 */
export function QuotaTab() {
  const { t } = useTranslation();
  const customers = useCustomers();
  return (
    <>
      <PageTitle>{t("pages.quota.title")}</PageTitle>
      <div className={styles.page}>
        <QueryView query={customers}>{(list) => <Table customers={list} />}</QueryView>
      </div>
    </>
  );
}
