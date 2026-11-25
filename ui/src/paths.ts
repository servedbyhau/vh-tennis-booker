/** The address of every screen; paths stay English in both languages. */
export const paths = {
  overview: "/",
  management: "/management",
  customers: "/management/customers",
  tickets: "/management/tickets",
  quota: "/management/quota",
  money: "/management/money",
  history: "/management/history",
  stats: "/management/stats",
} as const;

/**
 * The addresses of screens there are no more, and where they lead, keeping the query: a
 * `?run=` of the old History opens that run in the new one.
 */
export const OLD_PATHS = [
  ["/schedule", paths.overview],
  ["/history/*", paths.history],
  ["/activity", paths.history],
  ["/settings/*", paths.overview],
  ["/welcome", paths.overview],
  ["/guide", paths.overview],
] as const;
