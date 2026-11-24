/** The money's sums and words, apart from how they show (MoneyTab). */
import type { TFunction } from "i18next";
import type { Charge } from "../../api/types";
import { formatSlot } from "../../format";
import { sportName } from "../../quota";

/** Write `amount` VND as "150.000 đ". */
export function formatMoney(amount: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(amount)} đ`;
}

/** A customer's charges of the month, with their sums. */
export interface CustomerMoney {
  /** Its customer's id, `null` for charges of accounts removed since. */
  id: string | null;
  name: string;
  charges: Charge[];
  /** What is owed: the charges not cancelled, with a price. */
  owed: number;
  paid: number;
  /** Charges owed whose price is not known: no price for their sport. */
  unpriced: number;
}

/** Return what a charge counts for: nothing cancelled, free or without a price. */
export function owedOf(charge: Charge): number {
  return charge.cancelled || charge.free ? 0 : (charge.amount ?? 0);
}

/** Group `charges` by customer, the one who owes most first. */
export function byCustomer(charges: readonly Charge[], unknown: string): CustomerMoney[] {
  const found = new Map<string, CustomerMoney>();
  for (const charge of charges) {
    const key = charge.customer_id ?? `name:${charge.customer ?? ""}`;
    const item = found.get(key) ?? {
      id: charge.customer_id,
      name: charge.customer ?? unknown,
      charges: [],
      owed: 0,
      paid: 0,
      unpriced: 0,
    };
    item.charges.push(charge);
    item.owed += owedOf(charge);
    item.paid += charge.paid_at === null ? 0 : owedOf(charge);
    item.unpriced += !charge.cancelled && !charge.free && charge.amount === null ? 1 : 0;
    found.set(key, item);
  }
  return [...found.values()].sort((a, b) => b.owed - b.paid - (a.owed - a.paid));
}

/** Return the sums of the month: what is owed, paid and left, and the charges not priced yet. */
export function totalsOf(customers: readonly CustomerMoney[]) {
  const owed = customers.reduce((sum, item) => sum + item.owed, 0);
  const paid = customers.reduce((sum, item) => sum + item.paid, 0);
  const unpriced = customers.reduce((sum, item) => sum + item.unpriced, 0);
  return { owed, paid, left: owed - paid, unpriced };
}

/** Return "26/11" of a day of play "2026-11-26". */
function shortDay(day: string): string {
  return `${day.slice(8, 10)}/${day.slice(5, 7)}`;
}

/**
 * Return a customer's statement of the month as text to paste into a chat: a line a ticket, then
 * the sums. Cancelled tickets are left out.
 */
export function statementOf(t: TFunction, month: string, item: CustomerMoney): string {
  const lines = item.charges
    .filter((charge) => !charge.cancelled)
    .map((charge) => {
      const sport = sportName(t, charge.sport, charge.court);
      const amount = charge.free
        ? t("pages.money.free")
        : charge.amount === null
          ? "?"
          : formatMoney(charge.amount);
      return `${shortDay(charge.play_date)} ${formatSlot(charge.slot)} ${sport} ${charge.court.split(" - ")[0]}: ${amount}`;
    });
  return [
    t("pages.money.statementTitle", {
      month: `${month.slice(5)}/${month.slice(0, 4)}`,
      name: item.name,
    }),
    ...lines,
    t("pages.money.statementSums", {
      owed: formatMoney(item.owed),
      paid: formatMoney(item.paid),
      left: formatMoney(item.owed - item.paid),
    }),
  ].join("\n");
}
