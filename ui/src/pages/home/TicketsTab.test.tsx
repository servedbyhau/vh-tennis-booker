import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Ticket } from "../../api/types";
import i18n from "../../i18n";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { reply, requestsTo } from "../../test/backend";
import { step } from "../../test/liveSocket";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";
import { ticket } from "../../test/tickets";

/** Two machines' tickets around 15/10, with made-up codes. */
const TICKETS = [
  ticket("1000004", { play_date: "2026-10-17", device: 1, court: "S9 - Sân Pickleball" }),
  ticket("1000003", { slot: "19:00 - 20:00", has_photo: false, status: "processing" }),
  ticket("1000002", { slot: "18:00 - 19:00" }),
  ticket("1000001", { slot: "08:00 - 09:00", status: "cancelled", has_photo: false }),
  ticket("1000000", { play_date: "2026-10-12", status: "other", status_text: "Đã sử dụng" }),
];

/** Open the home screen with `tickets` and its tickets tab in front. */
async function openTab(tickets: Ticket[] = TICKETS) {
  const app = renderApp(paths.overview, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/tickets": reply(tickets),
  });
  // The panel is built anew once the status comes in.
  await screen.findByRole("region", { name: "Lần đặt tiếp theo" });
  fireEvent.click(screen.getByRole("tab", { name: "Quản lý" }));
  return app;
}

function panel() {
  return screen.getByRole("tabpanel", { name: "Quản lý" });
}

/** Each day listed, with the text of its tickets. */
async function days() {
  await within(panel()).findAllByRole("region");
  return within(panel())
    .queryAllByRole("region")
    .map((day) => [
      within(day).getByRole("heading").textContent,
      ...within(day)
        .getAllByRole("button")
        .map((row) => row.textContent),
    ]);
}

async function openTicket(name: RegExp) {
  fireEvent.click(await within(panel()).findByRole("button", { name }));
  return screen.getByRole("dialog");
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 9, 30));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Tickets list", () => {
  it("lists every machine's upcoming tickets by day, cancelled ones left out", async () => {
    await openTab();

    expect(await days()).toEqual([
      [
        "Thứ Sáu 16/102 vé",
        "18:00–19:00 · Tennis S6ĐÃ ĐĂNG KÝMáy 1 · 1000002Xem vé",
        "19:00–20:00 · Tennis S6ĐANG XỬ LÝMáy 1 · 1000003chưa có ảnh",
      ],
      ["Thứ Bảy 17/101 vé", "18:00–19:00 · Pickleball S9ĐÃ ĐĂNG KÝMáy 2 · 1000004Xem vé"],
    ]);
  });

  it("adds the cancelled tickets on request, without asking the backend again", async () => {
    const { fetch } = await openTab();
    await days();

    fireEvent.click(within(panel()).getByRole("checkbox", { name: "Gồm cả vé đã hủy" }));

    expect((await days())[0]?.[1]).toBe("08:00–09:00 · Tennis S6ĐÃ HỦYMáy 1 · 1000001chưa có ảnh");
    expect(requestsTo(fetch, "GET /api/tickets")).toBe(1);
  });

  it("lists the tickets past, a status of the app's own in its words", async () => {
    await openTab();
    await days();

    fireEvent.click(within(panel()).getByRole("button", { name: "Đã qua" }));

    expect(await days()).toEqual([
      ["Thứ Hai 12/101 vé", "18:00–19:00 · Tennis S6Đã sử dụngMáy 1 · 1000000Xem vé"],
    ]);
  });

  it("lists the tickets of one machine", async () => {
    await openTab();
    await days();
    const machines = within(panel()).getByRole("group", { name: "Vé của máy" });
    expect(
      within(machines)
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["Mọi máy", "Máy 1", "Máy 2"]);

    fireEvent.click(within(machines).getByRole("button", { name: "Máy 2" }));

    expect((await days()).map(([day]) => day)).toEqual(["Thứ Bảy 17/101 vé"]);
  });

  it("offers no machine to choose with one alone", async () => {
    await openTab([ticket("1000002")]);
    await days();
    expect(within(panel()).queryByRole("group", { name: "Vé của máy" })).not.toBeInTheDocument();
  });

  it("names the MuMu instance of a machine that has no tab any more", async () => {
    await openTab([ticket("1000002", { device: 7 })]);
    expect((await days())[0]?.[1]).toContain("MuMu 7 · 1000002");
  });

  it("keeps the filter while another tab is in front", async () => {
    await openTab();
    await days();
    fireEvent.click(within(panel()).getByRole("button", { name: "Đã qua" }));
    fireEvent.click(screen.getByRole("tab", { name: "Lịch sử" }));

    fireEvent.click(screen.getByRole("tab", { name: "Quản lý" }));

    expect((await days()).map(([day]) => day)).toEqual(["Thứ Hai 12/101 vé"]);
  });

  it("says when there is nothing to list", async () => {
    await openTab([]);
    expect(await within(panel()).findByText(/^Chưa có vé nào\./)).toBeInTheDocument();
  });

  it("says when the period has no ticket", async () => {
    await openTab([ticket("1000000", { play_date: "2026-10-12" })]);
    expect(await within(panel()).findByText("Không có vé nào sắp tới.")).toBeInTheDocument();
  });

  it("offers to try again when the tickets cannot be read", async () => {
    renderApp(paths.overview, { "GET /api/status": reply(overview()) });
    await screen.findByRole("region", { name: "Lần đặt tiếp theo" });
    fireEvent.click(screen.getByRole("tab", { name: "Quản lý" }));
    expect(await within(panel()).findByRole("button", { name: "Thử lại" })).toBeInTheDocument();
  });

  it("reads the tickets again once a run has read them in the app", async () => {
    const { fetch, live } = await openTab();
    await days();

    act(() => {
      live.current().open();
      live
        .current()
        .send(
          step(9, { kind: "tickets_saved", category: "step", data: { tickets: 4, photos: 2 } }),
        );
    });

    await waitFor(() => expect(requestsTo(fetch, "GET /api/tickets")).toBe(2));
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    renderApp(paths.overview, {
      "GET /api/status": reply(overview()),
      "GET /api/tickets": reply(TICKETS),
    });
    await screen.findByRole("region", { name: "Next booking" });
    fireEvent.click(screen.getByRole("tab", { name: "Manage" }));
    expect(
      await screen.findByRole("button", { name: /^18:00–19:00 · Tennis S6 ?REGISTERED/ }),
    ).toBeInTheDocument();
    await i18n.changeLanguage("vi");
  });
});

describe("Ticket dialog", () => {
  it("shows the ticket's picture alone and saves it under a name that tells it", async () => {
    await openTab();
    const dialog = await openTicket(/1000002/);
    const url = "/api/tickets/1000002/photo?seen=2026-10-14T06%3A01%3A12.000";

    expect(dialog).toHaveAccessibleName("18:00–19:00 · Tennis S6");
    expect(
      within(dialog).getByRole("img", { name: "Ảnh vé 18:00–19:00 · Tennis S6" }),
    ).toHaveAttribute("src", url);
    const save = within(dialog).getByRole("link", { name: "Lưu vé" });
    expect(save).toHaveAttribute("href", url);
    expect(save).toHaveAttribute("download", "2026-10-16 18h00-19h00 Tennis S6 1000002.png");
    expect(dialog.textContent).toBe("1/3");
  });

  it("moves through the tickets listed, with its buttons and the arrow keys", async () => {
    await openTab();
    const dialog = await openTicket(/1000002/);
    expect(within(dialog).getByText("1/3")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Vé trước" })).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Vé sau" }));
    expect(dialog).toHaveAccessibleName("19:00–20:00 · Tennis S6");

    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(dialog).toHaveAccessibleName("18:00–19:00 · Pickleball S9");
    fireEvent.keyDown(dialog, { key: "ArrowRight" }); // the last one stays
    expect(within(dialog).getByText("3/3")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Vé sau" })).toBeDisabled();

    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(within(dialog).getByText("2/3")).toBeInTheDocument();
  });

  it("says when a ticket has no picture", async () => {
    await openTab();
    const dialog = await openTicket(/1000003/);
    expect(within(dialog).queryByRole("img")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/^Vé này chưa có ảnh\./)).toBeInTheDocument();
    expect(within(dialog).queryByRole("link")).not.toBeInTheDocument(); // nothing to save
  });

  it("says when the picture does not open, for that ticket alone", async () => {
    await openTab();
    const dialog = await openTicket(/1000002/);
    fireEvent.error(within(dialog).getByRole("img"));
    expect(within(dialog).getByText("Không mở được ảnh vé.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("link")).not.toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(within(dialog).getByRole("img")).toBeInTheDocument();
  });

  it("closes with its button, Escape and a press beside it, and gives the focus back", async () => {
    await openTab();
    const row = await within(panel()).findByRole("button", { name: /1000002/ });
    row.focus();
    fireEvent.click(row);
    expect(screen.getByRole("dialog")).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Đóng" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(row).toHaveFocus();

    fireEvent.click(row);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(row);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("img"));
    expect(screen.getByRole("dialog")).toBeInTheDocument(); // a press inside keeps it
    fireEvent.click(screen.getByRole("dialog")); // between the picture and the buttons
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(row);
    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the keys working when a move takes the control pressed away", async () => {
    await openTab();
    const dialog = await openTicket(/1000002/);
    const next = within(dialog).getByRole("button", { name: "Vé sau" });
    next.focus();
    fireEvent.click(next);
    expect(next).toHaveFocus(); // there to press again
    fireEvent.click(next); // the last ticket: disabled from here on
    expect(dialog).toHaveFocus();

    const save = within(dialog).getByRole("link", { name: "Lưu vé" });
    save.focus();
    fireEvent.keyDown(save, { key: "ArrowLeft" }); // a ticket with nothing to save
    expect(dialog).toHaveFocus();
  });

  it("keeps Tab inside", async () => {
    await openTab();
    const dialog = await openTicket(/1000003/);
    const first = within(dialog).getByRole("button", { name: "Vé trước" });
    const last = within(dialog).getByRole("button", { name: "Vé sau" });

    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });
});
