import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuotaReading } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { reply } from "../../test/backend";
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

async function open() {
  renderApp(paths.quota, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/customers": reply(CUSTOMERS),
  });
  return within(await screen.findByRole("region", { name: "Hạn mức" }));
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
