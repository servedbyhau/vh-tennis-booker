/** The address of every screen; paths stay English in both languages. */
export const paths = {
  overview: "/",
  management: "/management",
  tickets: "/management/tickets",
  history: "/management/history",
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
  ["/guide", paths.overview],
  ["/welcome", paths.overview],
] as const;
