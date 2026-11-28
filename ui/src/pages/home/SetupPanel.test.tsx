import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Overview, RunSummary, ScheduleState } from "../../api/types";
import i18n from "../../i18n";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { overview } from "../../test/overview";
import { runSummary } from "../../test/runs";
import { settings } from "../../test/settings";

const BUSY = "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.";

/** A dry run of 15/10 at 09:12, as GET /api/runs?dry_run=true gives it. */
function dryRun(fields: Partial<RunSummary> = {}): RunSummary {
  return runSummary(31, {
    trigger: "dry_run",
    dry_run: true,
    started_at: "2026-10-15T09:12:00.000",
    finished_at: "2026-10-15T09:13:02.000",
    ...fields,
  });
}

interface Backend {
  status?: Overview;
  runs?: RunSummary[];
  extra?: Record<string, Reply>;
}

/** The Settings beside the ticket, once they are drawn. */
// Only stand-in backends here: a real PUT /api/schedule rewrites the Windows task.
async function openSetup({ status = overview(), runs = [], extra = {} }: Backend = {}) {
  const replies: Record<string, Reply> = {
    "GET /api/status": reply(status),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply(runs),
    "GET /api/accounts": reply([]),
    "GET /api/customers": reply([]),
    "GET /api/notifications": reply({ enabled: true, language: "vi" }),
    ...extra,
  };
  const app = renderApp(paths.overview, replies);
  const panel = within(screen.getByRole("region", { name: "Cài đặt" }));
  await panel.findByRole("button", { name: /^Chạy thử|^Dry run/ });
  return { replies, panel, ...app };
}

/** The schedule with some fields changed. */
function schedule(fields: Partial<ScheduleState>): Overview {
  const status = overview();
  return { ...status, schedule: { ...status.schedule, ...fields } };
}

/** The bodies of the requests sent, such as "PUT /api/schedule". */
async function bodies(
  fetch: Awaited<ReturnType<typeof openSetup>>["fetch"],
  key: string,
): Promise<unknown[]> {
  const sent = fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => `${request.method} ${new URL(request.url).pathname}` === key);
  return Promise.all(sent.map((request) => request.clone().json() as Promise<unknown>));
}

beforeEach(() => {
  // "Today" is 15/10.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SetupPanel", () => {
  it("holds the switches of every machine, then the machine shown", async () => {
    const { panel } = await openSetup();
    expect(await panel.findByRole("switch", { name: "Thông báo kết quả" })).toBeChecked();
    expect(panel.getByRole("switch", { name: "Tự đặt" })).toBeChecked();
    expect(panel.getByText("06:00 mỗi sáng, máy thức 05:50")).toBeVisible();
    const machine = within(await panel.findByRole("region", { name: "Máy 1" }));
    expect(await machine.findByRole("button", { name: /^Tài khoản/ })).toBeVisible();
    expect(machine.queryByRole("switch")).not.toBeInTheDocument(); // the first always books
  });

  it("follows the machine shown, leaving nothing of the last one", async () => {
    const { panel } = await openSetup();
    const tabs = within(await screen.findByRole("group", { name: "Máy" }));

    fireEvent.click(tabs.getByRole("button", { name: /^Máy 3/ }));
    const third = within(panel.getByRole("region", { name: "Máy 3" }));
    expect(third.getByRole("switch", { name: "Đặt sân bằng máy 3 (MuMu 2)" })).not.toBeChecked();

    fireEvent.click(tabs.getByRole("button", { name: /^Máy 1/ }));
    const first = within(panel.getByRole("region", { name: "Máy 1" }));
    expect(first.queryByRole("switch")).not.toBeInTheDocument();
    expect(panel.queryByText("Máy 3")).not.toBeInTheDocument();
  });

  it("has no tasks to tick: the app checks what it needs", async () => {
    const { panel } = await openSetup();
    expect(panel.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    renderApp(paths.overview, {
      "GET /api/status": reply(overview()),
      "GET /api/settings": reply(settings()),
      "GET /api/customers": reply([]),
    });
    const panel = within(screen.getByRole("region", { name: "Settings" }));
    expect(await panel.findByRole("switch", { name: "Auto-book" })).toBeChecked();
    expect(panel.getByRole("button", { name: "Dry run" })).toBeVisible();
    await i18n.changeLanguage("vi");
  });
});

describe("SetupPanel switches", () => {
  it("switches the result notification at once, in the UI's language", async () => {
    const { panel, fetch, replies } = await openSetup();
    replies["PUT /api/notifications"] = reply({ enabled: false, language: "vi" });

    fireEvent.click(await panel.findByRole("switch", { name: "Thông báo kết quả" }));

    await waitFor(async () =>
      expect(await bodies(fetch, "PUT /api/notifications")).toEqual([
        { enabled: false, language: "vi" },
      ]),
    );
  });

  it("lets the daily booking be switched on before any dry run", async () => {
    const { panel } = await openSetup({
      status: schedule({ enabled: false }),
    });
    expect(panel.getByRole("switch", { name: "Tự đặt" })).toBeEnabled();
    expect(panel.getByText("06:00 mỗi sáng, máy thức 05:50")).toBeVisible();
  });

  it("does not turn itself on, but asks for it", async () => {
    const { panel, fetch, replies } = await openSetup({ status: schedule({ enabled: false }) });
    const toggle = panel.getByRole("switch", { name: "Tự đặt" });
    expect(toggle).not.toBeChecked();
    expect(toggle.parentElement?.className).toMatch(/remind/);
    replies["PUT /api/schedule"] = reply(overview().schedule);

    fireEvent.click(toggle);

    await waitFor(async () =>
      expect(await bodies(fetch, "PUT /api/schedule")).toEqual([{ enabled: true }]),
    );
  });

  it("says why the daily booking was not switched", async () => {
    const { panel } = await openSetup({
      extra: { "PUT /api/schedule": reply({ error: "schedule", detail: "no" }, 502) },
    });
    fireEvent.click(panel.getByRole("switch", { name: "Tự đặt" }));
    expect(await panel.findByRole("alert")).toHaveTextContent(
      "Không đọc hoặc đổi được lịch hẹn giờ của Windows.",
    );
  });

  it("leaves the daily booking and the machines as they are while a run goes on", async () => {
    const { panel } = await openSetup({
      status: overview({ running: { trigger: "setup", pid: 4242, since: "21:00:00", runs: [] } }),
    });
    expect(panel.getByRole("switch", { name: "Tự đặt" })).toBeDisabled();
    const tabs = within(await screen.findByRole("group", { name: "Máy" }));
    fireEvent.click(tabs.getByRole("button", { name: /^Máy 2/ }));
    expect(panel.getByRole("switch", { name: /^Đặt sân bằng máy 2/ })).toBeDisabled();
  });
});

describe("SetupPanel dry run", () => {
  it("offers a first dry run while the app takes bookings", async () => {
    const { panel } = await openSetup();
    expect(await panel.findByText("Mất khoảng một phút, không đặt thật")).toBeVisible();
    const button = panel.getByRole("button", { name: "Chạy thử" });
    expect(button).toBeEnabled();
    expect(button).not.toHaveAttribute("title");
  });

  it("offers none while the app is closed, and says when it may", async () => {
    vi.setSystemTime(new Date(2026, 9, 15, 21, 30));
    const { panel } = await openSetup();

    const button = panel.getByRole("button", { name: "Chạy thử" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute(
      "title",
      "Chạy thử được từ 06:05 đến 21:00, khi app Vinhomes nhận đặt sân.",
    );
  });

  it("says when the last one passed", async () => {
    const { panel, fetch } = await openSetup({ runs: [dryRun()] });
    expect(await panel.findByText(/^Lần gần nhất/)).toHaveTextContent(
      "Lần gần nhất: sáng nay 09:12 · thành công",
    );
    const asked = fetch.mock.calls.map(([request]) => new URL(request.url).search);
    expect(asked).toContain("?dry_run=true&limit=1");
  });

  it("says why the last one did not pass", async () => {
    const full = { ok: false, reason: "Slot 15:00 - 16:00 is fully booked" };
    const slots = dryRun().slots.map((slot, index) => (index === 0 ? { ...slot, ...full } : slot));
    const { panel } = await openSetup({ runs: [dryRun({ status: "partial", booked: 1, slots })] });
    expect(await panel.findByText(/^Lần gần nhất/)).toHaveTextContent(
      "Lần gần nhất: sáng nay 09:12 · không qua: Hết chỗ",
    );
  });

  it("starts one", async () => {
    const started = reply({ pid: 4242, started_at: "2026-10-15T10:00:00.000" }, 202);
    const { panel, fetch } = await openSetup({ extra: { "POST /api/runs/dry-run": started } });
    fireEvent.click(panel.getByRole("button", { name: "Chạy thử" }));
    await waitFor(() => expect(requestsTo(fetch, "POST /api/runs/dry-run")).toBe(1));
  });

  it("says why one could not start", async () => {
    const held = reply({ error: "lock_held", detail: "Another run is in progress" }, 409);
    const { panel } = await openSetup({ extra: { "POST /api/runs/dry-run": held } });
    fireEvent.click(panel.getByRole("button", { name: "Chạy thử" }));
    expect(await panel.findByRole("alert")).toHaveTextContent(BUSY);
  });

  it("is locked while a run goes on, beside the run as it goes", async () => {
    const { panel } = await openSetup({
      status: overview({ running: { trigger: "dry_run", pid: 4242, since: "21:00:00", runs: [] } }),
    });
    expect(panel.getByText("Chạy thử tạm khóa cho tới khi xong")).toBeVisible();
    expect(panel.getByRole("button", { name: "Chạy thử" })).toBeDisabled();
  });
});

describe("SetupPanel machine without its MuMu instance", () => {
  it("says so, and switching it on leads to the Setup page's machines", async () => {
    const { panel, router, fetch } = await openSetup({
      extra: { "GET /api/mumu-instances": reply({ indexes: [0] }) },
    });
    const tabs = within(await screen.findByRole("group", { name: "Máy" }));
    fireEvent.click(tabs.getByRole("button", { name: /^Máy 2/ }));
    expect(await panel.findByText("Chưa có máy ảo MuMu")).toBeVisible();

    fireEvent.click(panel.getByRole("switch", { name: /^Đặt sân bằng máy 2/ }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/setup"));
    expect(router.state.location.search).toBe("?step=machines");
    expect(requestsTo(fetch, "PUT /api/instances/1")).toBe(0);
  });

  it("keeps no setup of the PC: the Setup page has it", async () => {
    const { panel } = await openSetup({
      extra: { "GET /api/keep-on": reply({ on: false, modern_standby: false }) },
    });
    expect(panel.queryByRole("switch", { name: "Giữ máy luôn chạy" })).not.toBeInTheDocument();
    expect(panel.queryByLabelText("File APK hoặc XAPK của app Vinhomes")).not.toBeInTheDocument();
  });
});

describe("SetupPanel book now", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("books for real after a question, while the app takes bookings", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 15, 14, 0));
    const { panel, fetch } = await openSetup({
      extra: { "POST /api/runs/now": reply({ pid: 1, started_at: "2026-10-15T14:00:00" }, 202) },
    });

    fireEvent.click(panel.getByRole("button", { name: "Đặt ngay" }));
    expect(panel.getByText(/^Đặt sân thật ngay bây giờ\?/)).toBeVisible();
    expect(requestsTo(fetch, "POST /api/runs/now")).toBe(0);
    fireEvent.click(panel.getByRole("button", { name: "Đặt" }));

    await waitFor(() => expect(requestsTo(fetch, "POST /api/runs/now")).toBe(1));
  });

  it("cannot book now while the app is closed", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 15, 22, 0));
    const { panel } = await openSetup();

    const button = panel.getByRole("button", { name: "Đặt ngay" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", expect.stringMatching(/đến 21:00/));
  });
});

describe("SetupPanel Zalo", () => {
  const LINKED = { linked: true, name: "Hậu", enabled: true };

  it("links a bot from its token, once someone wrote to it", async () => {
    const { panel, fetch } = await openSetup({
      extra: {
        "GET /api/zalo": reply({ linked: false, name: null, enabled: true }),
        "POST /api/zalo/link": reply(LINKED),
      },
    });
    fireEvent.click(await panel.findByRole("button", { name: "Kết nối" }));
    const form = within(panel.getByRole("form", { name: "Gửi về Zalo" }));
    expect(form.getByText(/^Nhắn một tin bất kỳ cho bot/)).toBeVisible();
    expect(form.getByRole("button", { name: "Kết nối" })).toBeDisabled();

    fireEvent.change(form.getByLabelText("Token của bot"), { target: { value: " 1234:abc-xyz " } });
    fireEvent.click(form.getByRole("button", { name: "Kết nối" }));

    expect(await panel.findByText("Gửi cho Hậu")).toBeVisible();
    expect(await bodies(fetch, "POST /api/zalo/link")).toEqual([{ token: "1234:abc-xyz" }]);
  });

  it("says why a link failed", async () => {
    const { panel } = await openSetup({
      extra: {
        "GET /api/zalo": reply({ linked: false, name: null, enabled: true }),
        "POST /api/zalo/link": reply({ error: "zalo_no_message", detail: "none" }, 409),
      },
    });
    fireEvent.click(await panel.findByRole("button", { name: "Kết nối" }));
    const form = within(panel.getByRole("form", { name: "Gửi về Zalo" }));
    fireEvent.change(form.getByLabelText("Token của bot"), { target: { value: "1234:abc-xyz" } });
    fireEvent.click(form.getByRole("button", { name: "Kết nối" }));

    expect(await form.findByRole("alert")).toHaveTextContent(/^Chưa thấy tin nhắn nào gửi cho bot/);
  });

  it("switches sending off, sends a test, and unlinks after a question", async () => {
    const { panel, fetch } = await openSetup({
      extra: {
        "GET /api/zalo": reply(LINKED),
        "PUT /api/zalo": reply({ ...LINKED, enabled: false }),
        "POST /api/zalo/test": { status: 204, body: null },
        "DELETE /api/zalo": { status: 204, body: null },
      },
    });
    fireEvent.click(await panel.findByRole("switch", { name: "Gửi về Zalo" }));
    await waitFor(() => expect(requestsTo(fetch, "PUT /api/zalo")).toBe(1));
    expect(await bodies(fetch, "PUT /api/zalo")).toEqual([{ enabled: false }]);

    fireEvent.click(panel.getByRole("button", { name: "Gửi tin thử qua Zalo" }));
    expect(await panel.findByText("Đã gửi tin thử cho Hậu")).toBeVisible();

    fireEvent.click(panel.getByRole("button", { name: "Bỏ kết nối Zalo" }));
    expect(panel.getByText("Bỏ kết nối? Muốn nối lại cần token.")).toBeVisible();
    expect(requestsTo(fetch, "DELETE /api/zalo")).toBe(0);
    fireEvent.click(panel.getByRole("button", { name: "Bỏ" }));
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/zalo")).toBe(1));
  });
});
