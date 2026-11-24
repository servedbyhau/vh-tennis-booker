/** Finding a customer by their name and facts, or by an account's name or phone number. */
import type { Customer, CustomerAccount } from "../../api/types";

/** Return `text` lower case and without Vietnamese marks, so "thuyen" finds "Thuyền". */
function plain(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/đ/g, "d").trim();
}

/** Return the digits of `query` when it is a phone number (digits, spaces, dots), else `null`. */
function digitsOf(query: string): string | null {
  return /^[\d\s.+-]+$/.test(query) ? query.replace(/\D/g, "") : null;
}

/** Return whether `text` holds what is searched: its digits for a number, else its words. */
function holds(text: string, query: string): boolean {
  const digits = digitsOf(query);
  return digits === null
    ? plain(text).includes(plain(query))
    : digits !== "" && text.replace(/\D/g, "").includes(digits);
}

/** Return whether `account` is what `query` searches for: by its name or phone number. */
export function accountFound(account: CustomerAccount, query: string): boolean {
  if (query.trim() === "") {
    return false;
  }
  return digitsOf(query) === null ? holds(account.label, query) : holds(account.phone ?? "", query);
}

/** Return whether `customer` is kept by `query`: every one while it is empty. */
export function customerFound(customer: Customer, query: string): boolean {
  if (query.trim() === "") {
    return true;
  }
  const facts = [customer.name, customer.representative, customer.contact, customer.note];
  return (
    facts.some((fact) => holds(fact, query)) ||
    customer.accounts.some((account) => accountFound(account, query))
  );
}
