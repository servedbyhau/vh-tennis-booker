import { call, client } from "./client";
import type {
  AccountSubdivision,
  DryRunStarted,
  Health,
  NewLogin,
  NotificationSettings,
  Overview,
  RunDetail,
  RunSummary,
  SavedLogin,
  ScheduleState,
  Settings,
  Step,
  Ticket,
  paths,
} from "./types";

/** Filters of the History list: `month` (YYYY-MM of the play date), `trigger`, paging. */
export type RunsQuery = NonNullable<paths["/api/runs"]["get"]["parameters"]["query"]>;
/** Filters of the Activity log: `category`, paging. */
export type EventsQuery = NonNullable<paths["/api/events"]["get"]["parameters"]["query"]>;

/** Check that the backend answers, and its version. */
export function getHealth(): Promise<Health> {
  return call(client.GET("/api/health"));
}

/** Read everything the Overview shows. */
export function getOverview(): Promise<Overview> {
  return call(client.GET("/api/status"));
}

/** List runs newest first. */
export function listRuns(query: RunsQuery = {}): Promise<RunSummary[]> {
  return call(client.GET("/api/runs", { params: { query } }));
}

/** Read one run with its slots, steps and technical log lines. */
export function getRun(runId: number): Promise<RunDetail> {
  return call(client.GET("/api/runs/{run_id}", { params: { path: { run_id: runId } } }));
}

/** List every machine's tickets, the latest day of play first. */
export function listTickets(): Promise<Ticket[]> {
  return call(client.GET("/api/tickets"));
}

/** List activity log steps newest first. */
export function listEvents(query: EventsQuery = {}): Promise<Step[]> {
  return call(client.GET("/api/events", { params: { query } }));
}

// openapi-fetch widens the response's [x, y] tuples (next_month_xy...) to number[]; the
// backend always sends two numbers, so the settings keep their schema type.

/** Read the booking settings. */
export function getSettings(): Promise<Settings> {
  return call(client.GET("/api/settings")) as Promise<Settings>;
}

/** Save the booking settings; invalid values fail with `invalid_settings` and `problems`. */
export function saveSettings(settings: Settings): Promise<Settings> {
  return call(client.PUT("/api/settings", { body: settings })) as Promise<Settings>;
}

/** Book with MuMu instance `mumuIndex` beside the first, or stop; answers the settings. */
export function switchInstance(mumuIndex: number, enabled: boolean): Promise<Settings> {
  return call(
    client.PUT("/api/instances/{mumu_index}", {
      params: { path: { mumu_index: mumuIndex } },
      body: { enabled },
    }),
  ) as Promise<Settings>;
}

/** Read the subdivision each MuMu instance's account told last, newest first. */
export function getAccounts(): Promise<AccountSubdivision[]> {
  return call(client.GET("/api/accounts"));
}

/** Tell whether a login is saved for MuMu instance `mumuIndex`, its phone number masked. */
export function getLogin(mumuIndex: number): Promise<SavedLogin> {
  return call(
    client.GET("/api/logins/{mumu_index}", { params: { path: { mumu_index: mumuIndex } } }),
  );
}

/** Save the login a run types in once the app logged out; the answer never holds it. */
export function saveLogin(mumuIndex: number, login: NewLogin): Promise<SavedLogin> {
  return call(
    client.PUT("/api/logins/{mumu_index}", {
      params: { path: { mumu_index: mumuIndex } },
      body: login,
    }),
  );
}

/** Remove the saved login of MuMu instance `mumuIndex`. */
export async function deleteLogin(mumuIndex: number): Promise<void> {
  await call(
    client.DELETE("/api/logins/{mumu_index}", { params: { path: { mumu_index: mumuIndex } } }),
  );
}

/** Read whether every run ends with a Windows notification, and its language. */
export function getNotifications(): Promise<NotificationSettings> {
  return call(client.GET("/api/notifications"));
}

/** Save the notification settings; they apply from the next run. */
export function saveNotifications(settings: NotificationSettings): Promise<NotificationSettings> {
  return call(client.PUT("/api/notifications", { body: settings }));
}

/** Switch the daily schedule on (needs a passed dry run) or off. */
export function switchSchedule(enabled: boolean): Promise<ScheduleState> {
  return call(client.PUT("/api/schedule", { body: { enabled } }));
}

/** Start a dry run in its own process; its steps arrive through the live feed. */
export function startDryRun(): Promise<DryRunStarted> {
  return call(client.POST("/api/runs/dry-run"));
}
