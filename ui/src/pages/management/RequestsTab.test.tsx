import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BookingRequest, Settings } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";
import { appliedTo } from "./requests";

const AN_ID = "a".repeat(32);
const AN = customer(AN_ID, { name: "Anh An", accounts: [account("b1", { device: 1 })] });
const BINH = customer("c".repeat(32), {
  name: "Chị Bình",
  accounts: [account("b2", { device: 2 })],
});

function request(fields: Partial<BookingRequest> = {}): BookingRequest {
  return {
    id: "d".repeat(32),
    customer_id: AN_ID,
    subdivision: "origami",
    sport: "pickleball",
    court: "S9 - Sân Pickleball",
    slots: ["18:00 - 19:00"],
    days: [0, 2, 4],
    machine: 1,
    active: true,
    note: "",
    created_at: "2026-11-24T10:00:00",
    ...fields,
  };
}

async function open(extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.requests, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/mumu-instances": reply({ indexes: [0, 1, 2] }),
    "GET /api/customers": reply([AN, BINH]),
    "GET /api/requests": reply([request()]),
    ...extra,
  });
  await screen.findByRole("region", { name: "Anh An" });
  return app;
}

describe("Requests", () => {
  it("lists each customer's requests with their court, slots, days and machine", async () => {
    await open();

    const card = within(screen.getByRole("region", { name: "Anh An" }));
    expect(card.getByText(/T2, T4, T6/)).toBeInTheDocument();
    expect(card.getByText(/Máy 2/)).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Chị Bình" })).getByText("Chưa có yêu cầu."),
    ).toBeInTheDocument();
  });

  it("shows the words of the form's switch beside it", async () => {
    await open();

    fireEvent.click(screen.getAllByRole("button", { name: /Thêm yêu cầu/ })[0]!);

    expect(await screen.findByText("Đang áp dụng")).toBeVisible();
    expect(screen.getByRole("switch", { name: "Đang áp dụng" })).toBeInTheDocument();
  });

  it("applies a request to its machine, switching it on first", async () => {
    const on: Settings = settings({
      instances: [
        {
          mumu_index: 1,
          slots: ["20:00 - 21:00"],
          subdivision: "",
          sport: "tennis",
          court: "S6 - Sân tennis",
          venue_keyword: "Origami",
          days: [],
        },
      ],
    });
    const app = await open({
      "PUT /api/instances/1": reply(on),
      "PUT /api/settings": reply(on),
    });

    fireEvent.click(screen.getByRole("button", { name: "Áp dụng cho máy" }));

    expect(await screen.findByText(/Đã áp dụng/)).toBeInTheDocument();
    expect(requestsTo(app.fetch, "PUT /api/instances/1")).toBe(1);
    const sent = app.fetch.mock.calls
      .map(([call]) => call)
      .find((call) => call.method === "PUT" && call.url.endsWith("/api/settings"));
    const body = (await sent?.clone().json()) as Settings;
    expect(body.instances[0]).toMatchObject({
      mumu_index: 1,
      sport: "pickleball",
      court: "S9 - Sân Pickleball",
      slots: ["18:00 - 19:00"],
      days: [0, 2, 4],
    });
  });

  it("says when the machine books with another customer's account", async () => {
    await open({ "GET /api/requests": reply([request({ machine: 2 })]) });

    expect(screen.getByText(/đang dùng tài khoản của khách khác/)).toBeInTheDocument();
  });

  it("adds a request with the slots and days chosen", async () => {
    const app = await open({ "POST /api/requests": reply(request(), 201) });

    fireEvent.click(screen.getByRole("button", { name: /Thêm yêu cầu/ }));
    const form = within(screen.getByRole("form", { name: "Thêm yêu cầu" }));
    fireEvent.click(form.getByRole("button", { name: "18:00–19:00" }));
    fireEvent.click(form.getByRole("button", { name: "T7" }));
    fireEvent.click(form.getByRole("button", { name: "Lưu" }));

    await waitFor(() => expect(requestsTo(app.fetch, "POST /api/requests")).toBe(1));
    const sent = app.fetch.mock.calls.map(([call]) => call).find((call) => call.method === "POST");
    expect(await sent?.clone().json()).toMatchObject({
      customer_id: AN_ID,
      slots: ["18:00 - 19:00"],
      days: [5],
    });
  });
});

describe("appliedTo", () => {
  it("sets the first machine's own choices at the top of the settings", () => {
    const applied = appliedTo(settings(), 0, request());

    expect([applied.sport, applied.court, applied.days]).toEqual([
      "pickleball",
      "S9 - Sân Pickleball",
      [0, 2, 4],
    ]);
  });
});
