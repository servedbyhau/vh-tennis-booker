/** The one form open on the accounts page: a customer's or an account's, a new one without `id`. */
export type Open =
  | { form: "customer"; id: string | null }
  | { form: "account"; customerId: string; id: string | null };
