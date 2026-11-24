import type { Customer, CustomerAccount } from "../api/types";

/** An account as GET /api/customers gives it, with made-up values. */
export function account(id: string, fields: Partial<CustomerAccount> = {}): CustomerAccount {
  return { id, label: "Căn A", phone: "0900000011", device: null, quota: [], ...fields };
}

/** A customer as GET /api/customers gives it, with made-up values. */
export function customer(id: string, fields: Partial<Customer> = {}): Customer {
  return { id, name: "Anh An", representative: "", contact: "", note: "", accounts: [], ...fields };
}
