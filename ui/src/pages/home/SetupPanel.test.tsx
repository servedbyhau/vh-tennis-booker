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

/** The Setup beside the ticket, once it is drawn. */
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
  const panel = within(screen.getByRole("region", { name: "Thiết lập" }));
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
    const panel = within(screen.getByRole("region", { name: "Setup" }));
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

  it("keeps the PC on while plugged in, and gives the values back when off", async () => {
    const { panel, fetch, replies } = await openSetup({
      extra: { "GET /api/keep-on": reply({ on: false, modern_standby: false }) },
    });
    const toggle = await panel.findByRole("switch", { name: "Giữ máy luôn chạy" });
    expect(toggle).not.toBeChecked();
    expect(panel.getByText("Máy có thể ngủ; app hẹn giờ đánh thức máy mỗi sáng")).toBeVisible();
    replies["PUT /api/keep-on"] = reply({ on: true, modern_standby: false });

    fireEvent.click(toggle);

    await waitFor(() => expect(toggle).toBeChecked());
    expect(await bodies(fetch, "PUT /api/keep-on")).toEqual([{ on: true }]);
    expect(panel.getByText(/màn hình tắt sau 5 phút$/)).toBeVisible();
  });

  it("has no keep-on switch when Windows could not be read", async () => {
    const { panel } = await openSetup();
    expect(panel.queryByRole("switch", { name: "Giữ máy luôn chạy" })).not.toBeInTheDocument();
  });

  it("lets the daily booking be switched on before any dry run", async () => {
    const { panel } = await openSetup({
      status: schedule({ enabled: false, dry_run_passed: false }),
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

describe("SetupPanel machine opening", () => {
  it("opens the MuMu of the machine shown", async () => {
    const { panel, fetch } = await openSetup({
      extra: { "POST /api/machines/0/open": { status: 204, body: null } },
    });

    fireEvent.click(panel.getByRole("button", { name: "Mở MuMu 0 để xem màn hình" }));

    await waitFor(() => expect(requestsTo(fetch, "POST /api/machines/0/open")).toBe(1));
  });

  it("says why it did not open", async () => {
    const { panel } = await openSetup({
      extra: {
        "POST /api/machines/0/open": reply({ error: "lock_held", detail: "busy" }, 409),
      },
    });

    fireEvent.click(panel.getByRole("button", { name: "Mở MuMu 0 để xem màn hình" }));

    expect(await panel.findByText(BUSY)).toBeVisible();
  });

  it("opens nothing while a run uses the machines", async () => {
    const running = { trigger: "scheduled", pid: 1, since: "2026-10-15T05:45:00", runs: [] };
    const { panel } = await openSetup({ status: { ...overview(), running } });

    expect(panel.getByRole("button", { name: "Mở MuMu 0 để xem màn hình" })).toBeDisabled();
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

describe("SetupPanel new machine", () => {
  const TASK = { code: null, machine: 0, started_at: "2026-10-15T10:00:00" };

  async function secondMachine(extra: Record<string, Reply>) {
    const app = await openSetup({
      extra: { "GET /api/mumu-instances": reply({ indexes: [0] }), ...extra },
    });
    const tabs = within(await screen.findByRole("group", { name: "Máy" }));
    fireEvent.click(tabs.getByRole("button", { name: /^Máy 2/ }));
    return app;
  }

  it("makes the MuMu instance of a machine that has none, after a question", async () => {
    const { panel, fetch } = await secondMachine({
      "POST /api/machines/new": reply({ ...TASK, running: true, exit_code: null }, 202),
      "GET /api/machines/new": reply({ ...TASK, running: false, exit_code: 0 }),
    });
    expect(await panel.findByText("Chưa có máy ảo MuMu")).toBeVisible();
    expect(panel.queryByRole("switch", { name: /^Đặt sân bằng máy 2/ })).not.toBeInTheDocument();

    fireEvent.click(panel.getByRole("button", { name: "Tạo máy ảo" }));
    expect(panel.getByText(/^Nhân bản máy ảo của Máy 1/)).toBeVisible();
    expect(requestsTo(fetch, "POST /api/machines/new")).toBe(0);
    fireEvent.click(panel.getByRole("button", { name: "Tạo" }));

    await waitFor(() => expect(requestsTo(fetch, "POST /api/machines/new")).toBe(1));
    // Once made, MuMu's instances are read again.
    await waitFor(() => expect(requestsTo(fetch, "GET /api/mumu-instances")).toBe(2), {
      timeout: 4000,
    });
  });

  it("says the PC lacks the RAM for it, and does not offer it", async () => {
    const { panel } = await secondMachine({
      "GET /api/machines/room": reply({ room: false, reason: "ram" }),
    });

    expect(await panel.findByText(/^Máy tính không đủ RAM cho máy ảo này/)).toBeVisible();
    expect(panel.getByRole("button", { name: "Tạo máy ảo" })).toBeDisabled();
  });

  it("says why it was not made", async () => {
    const { panel } = await secondMachine({
      "POST /api/machines/new": reply({ error: "no_room", detail: "8 GB" }, 409),
    });
    fireEvent.click(await panel.findByRole("button", { name: "Tạo máy ảo" }));
    fireEvent.click(panel.getByRole("button", { name: "Tạo" }));

    expect(await panel.findByRole("alert")).toHaveTextContent(/^Máy tính không đủ RAM/);
  });
});

describe("SetupPanel app install", () => {
  const APP_TASK = { code: null, machine: 0, started_at: "2026-10-15T09:12:00" };

  it("sends the file chosen and says when every machine has the app", async () => {
    const { panel, fetch } = await openSetup({
      extra: {
        "POST /api/app/install": reply({ ...APP_TASK, running: true, exit_code: null }, 202),
        "GET /api/app/install": reply({ ...APP_TASK, running: false, exit_code: 0 }),
      },
    });
    const file = new File(["PK"], "vinhomes.xapk", { type: "application/octet-stream" });

    fireEvent.change(panel.getByLabelText("File APK hoặc XAPK của app Vinhomes"), {
      target: { files: [file] },
    });

    await waitFor(() => expect(requestsTo(fetch, "POST /api/app/install")).toBe(1));
    expect(
      await panel.findByText("Đã cài app Vinhomes vào mọi máy ảo.", {}, { timeout: 4000 }),
    ).toBeVisible();
  });

  it("says a file not signed by the app was refused", async () => {
    const { panel } = await openSetup({
      extra: {
        "POST /api/app/install": reply({ ...APP_TASK, running: true, exit_code: null }, 202),
        "GET /api/app/install": reply({ ...APP_TASK, running: false, exit_code: 2 }),
      },
    });

    fireEvent.change(panel.getByLabelText("File APK hoặc XAPK của app Vinhomes"), {
      target: { files: [new File(["x"], "other.apk")] },
    });

    expect(await panel.findByRole("alert", {}, { timeout: 4000 })).toHaveTextContent(
      /^File này không phải app Vinhomes chính chủ/,
    );
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
