import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuotaReading } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

function read(sport: string, used: number, month = "2026-10"): QuotaReading {
  const utility = { tennis: "Sân Tennis", pickleball: "Sân Pickleball" }[sport] ?? sport;
  return { utility, sport, month, used, month_limit: 8, read_at: "2026-10-15T06:03:10.000" };
}

const CUSTOMERS = [
  customer("a1", {
    name: "Anh An",
    accounts: [
      account("b1", { device: 0, quota: [read("tennis", 7), read("pickleball", 2)] }),
      account("b2", { label: "Căn B", device: null, quota: [read("tennis", 8)] }),
    ],
  }),
];

async function open(extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.quota, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/customers": reply(CUSTOMERS),
    ...extra,
  });
  const board = within(await screen.findByRole("region", { name: "Hạn mức" }));
  return Object.assign(board, { fetch: app.fetch });
}

describe("Quota board", () => {
  it("shows every account's quota left of each sport in the month booked for", async () => {
    const board = await open();

    const rows = board.getAllByRole("row").map((row) => row.textContent);
    expect(rows[0]).toContain("Tennis");
    expect(rows[0]).toContain("Pickleball");
    expect(rows[1]).toContain("còn 1/8");
    expect(rows[1]).toContain("còn 6/8");
    expect(rows[2]).toContain("còn 0/8");
    // Read again only for the account on a machine.
    expect(board.getAllByRole("button", { name: "Đọc lại hạn mức" })).toHaveLength(1);
  });

  it("marks what is running out", async () => {
    const board = await open();

    expect(board.getByText("còn 1/8").className).toMatch(/warn/);
    expect(board.getByText("còn 0/8").className).toMatch(/bad/);
    expect(board.getByText("còn 6/8").className).toMatch(/good/);
  });
});

describe("Reading a quota again", () => {
  const RUNNING = { code: null, machine: 0, started_at: "2026-10-15T09:30:00", running: true };

  it("reads the quota of an account on a machine again, and says when it is done", async () => {
    const board = await open({
      "POST /api/machines/0/quota": reply({ ...RUNNING, exit_code: null }, 202),
      "GET /api/machines/quota": reply({ ...RUNNING, running: false, exit_code: 0 }),
    });

    fireEvent.click(board.getByRole("button", { name: "Đọc lại hạn mức" }));

    expect(await board.findByText(/^Đang đọc hạn mức trong app Vinhomes/)).toBeVisible();
    expect(await board.findByText("Đã đọc lại hạn mức.", {}, { timeout: 4000 })).toBeVisible();
    expect(requestsTo(board.fetch, "POST /api/machines/0/quota")).toBe(1);
    await waitFor(() => expect(requestsTo(board.fetch, "GET /api/customers")).toBeGreaterThan(1));
  });

  it("says why when it is refused", async () => {
    const board = await open({
      "POST /api/machines/0/quota": reply({ error: "lock_held", detail: "busy" }, 409),
      "GET /api/machines/quota": reply({}),
    });

    fireEvent.click(board.getByRole("button", { name: "Đọc lại hạn mức" }));

    expect(
      await board.findByText("Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại."),
    ).toBeVisible();
  });
});
