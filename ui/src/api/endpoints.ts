import { call, client } from "./client";
import type {
  AccountChange,
  AccountLogin,
  AccountSubdivision,
  CancelState,
  Customer,
  CustomerFields,
  DryRunStarted,
  Health,
  NewAccount,
  KeepOnState,
  NotificationSettings,
  Overview,
  ImportResult,
  RunDetail,
  RunSummary,
  ScheduleState,
  Settings,
  Step,
  TaskState,
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

/** Read a customers' .xlsx file and tell what it changes; with `apply`, make the changes. */
export function importCustomers({
  file,
  apply,
}: {
  file: Blob;
  apply: boolean;
}): Promise<ImportResult> {
  return call(
    client.POST("/api/customers/file", {
      params: { query: { apply } },
      // The workbook goes as it is: the schema calls its bytes a string.
      body: "",
      bodySerializer: () => file,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
    }),
  );
}

/** Mark ticket `code` sent to its customer, or not sent. */
export function markSent({ code, sent }: { code: string; sent: boolean }): Promise<void> {
  return call(
    client.PUT("/api/tickets/{code}/sent", { params: { path: { code } }, body: { sent } }),
  ).then(() => undefined);
}

/** Cancel ticket `code` in the app of the machine its account is on; it takes about a minute. */
export function cancelTicket(code: string): Promise<CancelState> {
  return call(client.POST("/api/tickets/{code}/cancel", { params: { path: { code } } }));
}

/** Read how the ticket cancel started last goes. */
export function getCancel(): Promise<CancelState> {
  return call(client.GET("/api/tickets/cancel"));
}

/** Read the quota of the account on MuMu instance `mumuIndex` again, in its app. */
export function readQuota(mumuIndex: number): Promise<TaskState> {
  return call(
    client.POST("/api/machines/{mumu_index}/quota", {
      params: { path: { mumu_index: mumuIndex } },
    }),
  );
}

/** Launch the MuMu instance `mumuIndex`, or bring its window to the front if it runs. */
export function openMachine(mumuIndex: number): Promise<void> {
  return call(
    client.POST("/api/machines/{mumu_index}/open", {
      params: { path: { mumu_index: mumuIndex } },
    }),
  ).then(() => undefined);
}

/** Read how the quota read started last goes. */
export function getQuotaTask(): Promise<TaskState> {
  return call(client.GET("/api/machines/quota"));
}

/** Install the Vinhomes app from `file` (an APK or XAPK, sent as it is) on every MuMu instance. */
export function startAppInstall(file: Blob): Promise<TaskState> {
  return call(
    client.POST("/api/app/install", {
      // The file goes as it is: the schema calls its bytes a string.
      body: "",
      bodySerializer: () => file,
      headers: { "Content-Type": "application/octet-stream" },
    }),
  );
}

/** Read how the app install started last from the app goes, or how it ended. */
export function getAppInstallTask(): Promise<TaskState> {
  return call(client.GET("/api/app/install"));
}

/** Make another machine's MuMu instance, a copy of the first machine's. */
export function startNewMachine(): Promise<TaskState> {
  return call(client.POST("/api/machines/new"));
}

/** Read how the MuMu instance made last from the app goes, or how it ended. */
export function getNewMachineTask(): Promise<TaskState> {
  return call(client.GET("/api/machines/new"));
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

/** List the MuMu instances on this PC; empty when MuMuManager does not answer. */
export function getMumuInstances(): Promise<number[]> {
  return call(client.GET("/api/mumu-instances")).then((answer) => answer.indexes);
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

/** Read the customers, each with their accounts. */
export function listCustomers(): Promise<Customer[]> {
  return call(client.GET("/api/customers"));
}

/** Add a customer without accounts. */
export function addCustomer(fields: CustomerFields): Promise<Customer> {
  return call(client.POST("/api/customers", { body: fields }));
}

/** Change a customer's name and note. */
export function changeCustomer(id: string, fields: CustomerFields): Promise<Customer> {
  return call(
    client.PUT("/api/customers/{customer_id}", {
      params: { path: { customer_id: id } },
      body: fields,
    }),
  );
}

/** Remove a customer with their accounts, taken from the machines they are attached to. */
export async function removeCustomer(id: string): Promise<void> {
  await call(
    client.DELETE("/api/customers/{customer_id}", {
      params: { path: { customer_id: id }, query: { detach: true } },
    }),
  );
}

/** Add an account to a customer; the answer never holds its password. */
export function addAccount(customerId: string, account: NewAccount): Promise<Customer> {
  return call(
    client.POST("/api/customers/{customer_id}/accounts", {
      params: { path: { customer_id: customerId } },
      body: account,
    }),
  );
}

/** Read the saved login of an account, whole, for the form that changes it. */
export function getAccountLogin(id: string): Promise<AccountLogin> {
  return call(
    client.GET("/api/customer-accounts/{account_id}/login", {
      params: { path: { account_id: id } },
    }),
  );
}

/** Change an account's label and, unless `null`, its phone number and password. */
export function changeAccount(id: string, change: AccountChange): Promise<Customer> {
  return call(
    client.PUT("/api/customer-accounts/{account_id}", {
      params: { path: { account_id: id } },
      body: change,
    }),
  );
}

/** Remove an account, taken from the machine it is attached to. */
export async function removeAccount(id: string): Promise<void> {
  await call(
    client.DELETE("/api/customer-accounts/{account_id}", {
      params: { path: { account_id: id }, query: { detach: true } },
    }),
  );
}

/** Let MuMu instance `mumuIndex` book with the account from its next run on. */
export function attachAccount(mumuIndex: number, accountId: string): Promise<Customer> {
  return call(
    client.PUT("/api/machines/{mumu_index}/account", {
      params: { path: { mumu_index: mumuIndex } },
      body: { account_id: accountId },
    }),
  );
}

/** Let MuMu instance `mumuIndex` book with whichever account its app has logged in. */
export async function detachAccount(mumuIndex: number): Promise<void> {
  await call(
    client.DELETE("/api/machines/{mumu_index}/account", {
      params: { path: { mumu_index: mumuIndex } },
    }),
  );
}

/** Read whether the PC is kept on while plugged in. */
export function getKeepOn(): Promise<KeepOnState> {
  return call(client.GET("/api/keep-on"));
}

/** Keep the PC on while plugged in, or give back the power values it had. */
export function switchKeepOn(on: boolean): Promise<KeepOnState> {
  return call(client.PUT("/api/keep-on", { body: { on } }));
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

/** Book for real now: before the start time it gets ready and books at it. */
export function startBooking(): Promise<DryRunStarted> {
  return call(client.POST("/api/runs/now"));
}

/** Start a dry run in its own process; its steps arrive through the live feed. */
export function startDryRun(): Promise<DryRunStarted> {
  return call(client.POST("/api/runs/dry-run"));
}
