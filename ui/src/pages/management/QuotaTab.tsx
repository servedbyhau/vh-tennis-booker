import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { useCustomers } from "../../api/queries";
import type { Customer, CustomerAccount, QuotaReading } from "../../api/types";
import { IconButton } from "../../components/IconButton";
import { PageTitle } from "../../components/PageTitle";
import { QueryView } from "../../components/QueryView";
import { EmptyState } from "../../components/States";
import { useMachines } from "../../machines";
import { leftOf, sportName, useBookingMonth } from "../../quota";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";
import layout from "./CustomersTab.module.css";
import { CustomerList } from "./CustomerList";
import { customerFound } from "./customerSearch";
import { useQuotaRefresh } from "./quotaRefresh";
import own from "./QuotaTab.module.css";

/** A customer is marked once an account has this few bookings left of a sport, or none. */
const FEW_LEFT = 1;

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

/** Return the sports read in `month` for `accounts`, each once, in the order first met. */
function columnsOf(accounts: readonly CustomerAccount[], month: string): Column[] {
  const found = new Map<string, Column>();
  for (const account of accounts) {
    for (const reading of account.quota) {
      const key = reading.sport ?? reading.utility;
      if (reading.month === month && !found.has(key)) {
        found.set(key, { key, sport: reading.sport ?? null, utility: reading.utility });
      }
    }
  }
  return [...found.values()];
}

/** Return whether one of `customer`'s accounts has little or nothing left of a sport in `month`. */
function runningOut(customer: Customer, month: string): boolean {
  return customer.accounts.some((account) =>
    account.quota.some((reading) => reading.month === month && leftOf(reading) <= FEW_LEFT),
  );
}

/** One cell: the bookings made of a sport out of its limit, "Full" once none is left. */
function Used({ reading }: { reading: QuotaReading | undefined }) {
  const { t } = useTranslation();
  const f = useFormat();
  if (reading === undefined) {
    return <span className={styles.muted}>–</span>;
  }
  const used = Math.min(reading.used, reading.month_limit);
  return (
    <span
      className={styles.chip}
      title={t("pages.quota.readAt", {
        time: f.time(reading.read_at),
        day: f.shortDate(reading.read_at),
      })}
    >
      {leftOf(reading) === 0
        ? t("pages.quota.full")
        : t("pages.quota.used", { used, limit: reading.month_limit })}
    </span>
  );
}

interface RowProps {
  account: CustomerAccount;
  columns: Column[];
  month: string;
}

/** One account in a row: its name and number, what it booked of each sport, and a read again. */
function Row({ account, columns, month }: RowProps) {
  const { t } = useTranslation();
  const refresh = useQuotaRefresh(account.device);
  const machine = useMachines().find((item) => item.mumuIndex === account.device);
  const machineText =
    machine === undefined
      ? t("pages.quota.machine", { index: account.device })
      : t("pages.ticket.instanceName", { number: machine.place + 1 });
  return (
    <tr>
      <td>
        {account.label}
        {account.label !== "" && <br />}
        <span className={`${styles.muted} ${styles.mono}`}>{account.phone ?? ""}</span>
      </td>
      {columns.map((column) => (
        <td key={column.key}>
          <Used
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
            label={t("pages.quota.readOn", { machine: machineText })}
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

interface TableProps {
  customer: Customer;
  month: string;
  months: string[];
  onMonth: (month: string) => void;
}

/** The table of a customer's accounts and sports in one month, with the months to choose from. */
function Table({ customer, month, months, onMonth }: TableProps) {
  const { t } = useTranslation();
  const columns = columnsOf(customer.accounts, month);
  return (
    <section aria-label={customer.name} className={own.body}>
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
                onClick={() => onMonth(item)}
              >
                {`${item.slice(5)}/${item.slice(0, 4)}`}
              </button>
            ))}
          </span>
        )}
      </div>
      {customer.accounts.length === 0 ? (
        <p className={styles.muted}>{t("pages.customers.noAccounts")}</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>{t("pages.quota.account")}</th>
              {columns.map((column) => (
                <th key={column.key}>{sportName(t, column.sport, column.utility)}</th>
              ))}
              <th>
                <span className="visually-hidden">{t("quota.refresh.button")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {customer.accounts.map((account) => (
              <Row key={account.id} account={account} columns={columns} month={month} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

interface ColumnsProps {
  customers: readonly Customer[];
  /** The customer in the address, else the first found. */
  chosen: string | null;
  onChoose: (id: string) => void;
}

/** The customers on the left, marked when running out; the chosen one's table beside them. */
function Columns({ customers, chosen, onChoose }: ColumnsProps) {
  const { t } = useTranslation();
  const booking = useBookingMonth();
  const [query, setQuery] = useState("");
  const [chosenMonth, setChosenMonth] = useState<string | null>(null);
  const months = monthsOf(customers);
  const month = chosenMonth ?? booking ?? months[0];
  if (month === undefined || customers.length === 0) {
    return <EmptyState>{t("pages.quota.empty")}</EmptyState>;
  }
  const found = customers.filter((customer) => customerFound(customer, query));
  const shown = found.find((customer) => customer.id === chosen) ?? found[0];
  return (
    <div className={layout.columns}>
      <CustomerList
        customers={found}
        shown={shown?.id ?? null}
        onChoose={onChoose}
        query={query}
        onQuery={setQuery}
        marked={(customer) => runningOut(customer, month)}
      />
      <div className={layout.detail}>
        {shown === undefined ? (
          <div className={own.body}>
            <EmptyState>{t("pages.customers.noMatch")}</EmptyState>
          </div>
        ) : (
          <Table customer={shown} month={month} months={months} onMonth={setChosenMonth} />
        )}
      </div>
    </div>
  );
}

/**
 * What each customer's accounts booked of each sport's quota in a month, as the runs and the
 * reads asked for last saw it: the customers on the left, the one chosen in a table beside them,
 * a row an account, a column a sport. The address keeps the choice.
 */
export function QuotaTab() {
  const { t } = useTranslation();
  const customers = useCustomers();
  const [params, setParams] = useSearchParams();
  return (
    <>
      <PageTitle>{t("pages.quota.title")}</PageTitle>
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
