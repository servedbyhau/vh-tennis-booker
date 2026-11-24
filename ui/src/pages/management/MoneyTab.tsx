import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useChangeCharge, useMarkFree, useMarkPaid, useSavePrices } from "../../api/mutations";
import { useCharges, usePrices } from "../../api/queries";
import type { Charge, Prices } from "../../api/types";
import { isSport, type Sport } from "../../booking";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { IconButton } from "../../components/IconButton";
import { PageTitle } from "../../components/PageTitle";
import { Switch } from "../../components/Switch";
import { Loading } from "../../components/States";
import { localToday } from "../../format";
import texts from "../../i18n/locales/vi.json";
import { sportName } from "../../quota";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";
import { byCustomer, type CustomerMoney, formatMoney, statementOf, totalsOf } from "./money";

/** Every sport the language files name, for the price list. */
const SPORTS: Sport[] = Object.keys(texts.sports).filter(isSport);

/** "11/2026" of "2026-11". */
function monthText(month: string): string {
  return `${month.slice(5)}/${month.slice(0, 4)}`;
}

/** A charge's amount, set by hand with a small form. */
function Amount({ charge }: { charge: Charge }) {
  const { t } = useTranslation();
  const change = useChangeCharge();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(charge.amount ?? ""));
  if (charge.cancelled) {
    return <span className={styles.muted}>{t("pages.money.cancelled")}</span>;
  }
  if (charge.free) {
    return <span className={styles.muted}>{t("pages.money.free")}</span>;
  }
  if (editing) {
    return (
      <form
        className={styles.chips}
        onSubmit={(event) => {
          event.preventDefault();
          const amount = Number(value.replace(/\D/g, ""));
          change.mutate(
            {
              code: charge.code,
              change:
                value.trim() === "" ? { reset_amount: true } : { amount, reset_amount: false },
            },
            { onSuccess: () => setEditing(false) },
          );
        }}
      >
        <input
          aria-label={t("pages.money.amount")}
          inputMode="numeric"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          size={9}
        />
        <Button type="submit" disabled={change.isPending}>
          {t("pages.money.save")}
        </Button>
      </form>
    );
  }
  return (
    <span className={styles.chips}>
      <span className={styles.number}>
        {charge.amount === null ? t("pages.money.noPrice") : formatMoney(charge.amount)}
      </span>
      {charge.set_by_hand && <span className={styles.muted}>{t("pages.money.byHand")}</span>}
      <IconButton
        icon="edit"
        label={t("pages.money.editAmount")}
        onClick={() => {
          setValue(String(charge.amount ?? ""));
          setEditing(true);
        }}
      />
    </span>
  );
}

/** One customer's month: a row a ticket, paid or not, and the sums with what to do. */
function CustomerCard({
  item,
  month,
  free,
}: {
  item: CustomerMoney;
  month: string;
  free: boolean;
}) {
  const { t } = useTranslation();
  const f = useFormat();
  const pay = useMarkPaid();
  const change = useChangeCharge();
  const markFree = useMarkFree();
  const [copied, setCopied] = useState<"copied" | "failed" | null>(null);
  const unpaid = item.charges.filter(
    (charge) => !charge.cancelled && !charge.free && charge.paid_at === null,
  );
  const left = item.owed - item.paid;
  return (
    <section aria-label={item.name} className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{item.name}</h2>
        <span className={`${styles.chip} ${left > 0 ? styles.warn : styles.good}`}>
          {left > 0
            ? t("pages.money.leftToPay", { left: formatMoney(left) })
            : t("pages.money.allPaid")}
        </span>
      </div>
      {item.id !== null && (
        <Switch
          label={t("pages.money.freeLabel")}
          checked={free}
          disabled={markFree.isPending}
          onChange={(value) => item.id !== null && markFree.mutate({ id: item.id, free: value })}
        />
      )}
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{t("pages.money.day")}</th>
            <th>{t("pages.money.court")}</th>
            <th>{t("pages.money.amount")}</th>
            <th>{t("pages.money.paid")}</th>
          </tr>
        </thead>
        <tbody>
          {item.charges.map((charge) => (
            <tr key={charge.code} className={charge.cancelled ? styles.muted : undefined}>
              <td>
                {f.shortDay(charge.play_date)}
                <br />
                <span className={styles.muted}>
                  {f.slot(charge.slot)}
                  {charge.golden && ` · ${t("pages.money.golden")}`}
                </span>
              </td>
              <td>
                {sportName(t, charge.sport, charge.court)}{" "}
                <span className={styles.muted}>{charge.court.split(" - ")[0]}</span>
              </td>
              <td>
                <Amount key={`${charge.code}-${charge.amount}`} charge={charge} />
              </td>
              <td>
                {!charge.cancelled && !charge.free && (
                  <button
                    type="button"
                    aria-pressed={charge.paid_at !== null}
                    aria-label={t("pages.money.markPaid", { day: f.shortDay(charge.play_date) })}
                    className={`${styles.chip} ${charge.paid_at === null ? "" : styles.good}`}
                    disabled={change.isPending}
                    onClick={() =>
                      change.mutate({
                        code: charge.code,
                        change: { paid: charge.paid_at === null, reset_amount: false },
                      })
                    }
                  >
                    <Icon name={charge.paid_at === null ? "clock" : "check"} />
                    {t(charge.paid_at === null ? "pages.money.unpaid" : "pages.money.paidMark")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.muted}>
        {t("pages.money.sums", {
          owed: formatMoney(item.owed),
          paid: formatMoney(item.paid),
          count: item.charges.filter((charge) => !charge.cancelled).length,
        })}
        {item.unpriced > 0 && ` · ${t("pages.money.unpriced", { count: item.unpriced })}`}
      </p>
      {(pay.isError || change.isError) && (
        <p role="alert" className={styles.muted}>
          {errorMessage(t, pay.error ?? change.error)}
        </p>
      )}
      <div className={styles.actions}>
        <Button
          disabled={unpaid.length === 0 || pay.isPending}
          onClick={() => pay.mutate({ codes: unpaid.map((charge) => charge.code), paid: true })}
        >
          <Icon name="check" /> {t("pages.money.payAll")}
        </Button>
        <Button
          onClick={() => {
            void navigator.clipboard.writeText(statementOf(t, month, item)).then(
              () => setCopied("copied"),
              () => setCopied("failed"),
            );
          }}
        >
          <Icon name="copy" /> {t("pages.money.copy")}
        </Button>
        {copied !== null && (
          <span role="status" className={styles.muted}>
            {t(copied === "copied" ? "pages.money.copied" : "pages.money.copyFailed")}
          </span>
        )}
      </div>
    </section>
  );
}

/** The price list: the golden hours and a normal and golden price a sport. */
function PriceCard({ prices }: { prices: Prices }) {
  const { t } = useTranslation();
  const save = useSavePrices();
  const [from, setFrom] = useState(prices.golden_from);
  const [to, setTo] = useState(prices.golden_to);
  const [values, setValues] = useState<Record<string, { normal: string; golden: string }>>(() =>
    Object.fromEntries(
      prices.prices.map((price) => [
        price.sport,
        { normal: String(price.normal), golden: String(price.golden) },
      ]),
    ),
  );
  const set = (sport: string, field: "normal" | "golden", value: string) =>
    setValues((old) => ({
      ...old,
      [sport]: { normal: "", golden: "", ...old[sport], [field]: value.replace(/\D/g, "") },
    }));
  return (
    <section aria-labelledby="money-prices" className={styles.card}>
      <h2 id="money-prices" className={styles.sectionTitle}>
        {t("pages.money.pricesTitle")}
      </h2>
      <form
        className={styles.lines}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate({
            golden_from: from,
            golden_to: to,
            prices: SPORTS.flatMap((sport) => {
              const value = values[sport];
              if (value === undefined || (value.normal === "" && value.golden === "")) {
                return [];
              }
              const normal = Number(value.normal || value.golden);
              return [{ sport, normal, golden: Number(value.golden || value.normal) }];
            }),
          });
        }}
      >
        <label className={styles.line}>
          <span className={styles.label}>{t("pages.money.goldenHours")}</span>
          <input type="time" value={from} onChange={(event) => setFrom(event.target.value)} />
          –
          <input type="time" value={to} onChange={(event) => setTo(event.target.value)} />
        </label>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>{t("pages.money.sport")}</th>
              <th>{t("pages.money.normal")}</th>
              <th>{t("pages.money.goldenPrice")}</th>
            </tr>
          </thead>
          <tbody>
            {SPORTS.map((sport) => (
              <tr key={sport}>
                <td>{t(`sports.${sport}`)}</td>
                {(["normal", "golden"] as const).map((field) => (
                  <td key={field}>
                    <input
                      aria-label={`${t(`sports.${sport}`)} ${t(field === "normal" ? "pages.money.normal" : "pages.money.goldenPrice")}`}
                      inputMode="numeric"
                      size={9}
                      value={values[sport]?.[field] ?? ""}
                      onChange={(event) => set(sport, field, event.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {save.isError && (
          <p role="alert" className={styles.muted}>
            {errorMessage(t, save.error)}
          </p>
        )}
        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            {t("pages.money.savePrices")}
          </Button>
          {save.isSuccess && (
            <span role="status" className={styles.muted}>
              {t("pages.money.saved")}
            </span>
          )}
        </div>
      </form>
    </section>
  );
}

/**
 * What the customers owe for the tickets booked for them, a month of play at a time: the sums,
 * each customer's tickets with their price and whether paid, the statement to send, and the
 * price list.
 */
export function MoneyTab() {
  const { t } = useTranslation();
  const [month, setMonth] = useState(localToday().slice(0, 7));
  const charges = useCharges(month);
  const prices = usePrices();
  const months = [...new Set([month, ...(charges.data?.months ?? [])])].sort().reverse();
  const customers = byCustomer(charges.data?.charges ?? [], t("pages.tickets.unknown"));
  const { owed, paid, left } = totalsOf(customers);
  const free = new Set(charges.data?.free_customers ?? []);
  return (
    <>
      <PageTitle>{t("pages.money.title")}</PageTitle>
      <div className={styles.page}>
        <div role="group" aria-label={t("pages.money.months")} className={styles.chips}>
          {months.map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={item === month}
              className={`${styles.chip} ${item === month ? styles.good : ""}`}
              onClick={() => setMonth(item)}
            >
              {t("pages.money.month", { month: monthText(item) })}
            </button>
          ))}
        </div>
        <div className={styles.figures}>
          {(
            [
              [owed, "pages.money.owed"],
              [paid, "pages.money.paidSum"],
              [left, "pages.money.left"],
            ] as const
          ).map(([value, label]) => (
            <div key={label} className={styles.figure}>
              <span className={styles.figureValue}>{formatMoney(value)}</span>
              <span className={styles.figureLabel}>{t(label)}</span>
            </div>
          ))}
        </div>
        <div className={styles.wide}>
          <div className={styles.column}>
            {charges.isPending ? (
              <Loading />
            ) : customers.length === 0 ? (
              <p className={styles.card}>{t("pages.money.none")}</p>
            ) : (
              customers.map((item) => (
                <CustomerCard
                  key={item.id ?? item.name}
                  item={item}
                  month={month}
                  free={item.id !== null && free.has(item.id)}
                />
              ))
            )}
          </div>
          {prices.data === undefined ? <Loading /> : <PriceCard prices={prices.data} />}
        </div>
      </div>
    </>
  );
}
