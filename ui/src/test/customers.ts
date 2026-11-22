import type { Customer, CustomerAccount } from "../api/types";

/** An account as GET /api/customers gives it, with made-up values. */
export function account(id: string, fields: Partial<CustomerAccount> = {}): CustomerAccount {
  return { id, label: "Căn A", phone: "09••••••11", device: null, ...fields };
}

/** A customer as GET /api/customers gives it, with made-up values. */
export function customer(id: string, fields: Partial<Customer> = {}): Customer {
  return { id, name: "Anh An", note: "", accounts: [], ...fields };
}
