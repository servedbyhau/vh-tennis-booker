/** The address of every screen; paths stay English in both languages. */
export const paths = {
  overview: "/",
  management: "/management",
  machines: "/management/machines",
  customers: "/management/customers",
  tickets: "/management/tickets",
  history: "/management/history",
  guide: "/guide",
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
  ["/welcome", paths.guide],
] as const;
