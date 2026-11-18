import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Overview } from "../../api/types";
import { STORAGE_KEY } from "../../manualSteps";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

const ALL = { mumu: true, app: true, login: true };

/** Render the home screen on its Setup tab: a step is left, so it opens there. */
function renderSetup(status: Overview = overview(), extra: Record<string, Reply> = {}) {
  const replies: Record<string, Reply> = {
    "GET /api/status": reply(status),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/notifications": reply({ enabled: true, language: "vi" }),
    ...extra,
  };
  return { replies, ...renderApp(paths.overview, replies) };
}

/** The Setup tab, whatever its count. */
function setupTab() {
  return screen.findByRole("tabpanel", { name: /^Thiết lập/ });
}

beforeEach(() => {
  // "Today" is 15/10.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SetupTab first use", () => {
  it("starts with how to use it, while anything is left", async () => {
    renderSetup();

    const tab = await setupTab();
    const start = within(tab).getByRole("region", {
      name: "Court Booker đặt sân thay bạn lúc 06:00 mỗi sáng, kể cả khi bạn ngủ",
    });
    expect(
      within(start)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([
      "Làm các việc thiết lập bên dưới, một lần.",
      "Chọn môn, sân và khung giờ trên vé bên trái.",
      'Bấm "Chạy thử ngay", đạt thì bật "Tự đặt".',
    ]);
  });

  it("keeps how to use it in the guide once everything is set up", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ALL));
    renderSetup();
    // Everything is set up: the panel opens on the History once the status is in.
    await within(screen.getByRole("banner")).findByText(/Sẵn sàng/);
    fireEvent.click(screen.getByRole("tab", { name: "Thiết lập" }));

    const tab = await setupTab();
    expect(within(tab).queryByRole("region", { name: /Court Booker đặt sân thay bạn/ })).toBeNull();
    expect(within(tab).getByText("Cách dùng trong 3 bước")).toBeInTheDocument();
  });
});

describe("SetupTab steps the user does", () => {
  it("ticks a step, keeps it in the browser and counts down the tasks", async () => {
    renderSetup();
    const tab = await setupTab();
    expect(screen.getByRole("tab", { name: "Thiết lập, còn 3 việc" })).toBeInTheDocument();

    fireEvent.click(within(tab).getByRole("checkbox", { name: /Đã cài MuMu Player/ }));

    expect(within(tab).getByRole("checkbox", { name: /Đã cài MuMu Player/ })).toBeChecked();
    expect(screen.getByRole("tab", { name: "Thiết lập, còn 2 việc" })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "")).toEqual({
      mumu: true,
      app: false,
      login: false,
    });
    expect(
      within(screen.getByRole("banner")).getByText(/Còn 2 việc thiết lập/),
    ).toBeInTheDocument();
  });

  it("checks nothing with the backend", async () => {
    const { fetch } = renderSetup();
    const tab = await setupTab();

    fireEvent.click(within(tab).getByRole("checkbox", { name: /Đã đăng nhập app Vinhomes/ }));

    expect(requestsTo(fetch, "GET /api/setup")).toBe(0);
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });
});

describe("SetupTab saved login", () => {
  const NONE = { mumu_index: 0, saved: false, phone: null };
  const SAVED = { mumu_index: 0, saved: true, phone: "09••••••79" };

  it("shows a saved login by its masked phone, never its password", async () => {
    renderSetup(overview(), { "GET /api/logins/0": reply(SAVED) });
    const tab = await setupTab();

    expect(await within(tab).findByText("Đã lưu cho số 09••••••79")).toBeInTheDocument();
    expect(within(tab).queryByLabelText("Mật khẩu")).not.toBeInTheDocument();
  });

  it("saves a login and empties the form", async () => {
    const { fetch } = renderSetup(overview(), {
      "GET /api/logins/0": reply(NONE),
      "PUT /api/logins/0": reply(SAVED),
    });
    const tab = await setupTab();

    fireEvent.change(await within(tab).findByLabelText("Số điện thoại"), {
      target: { value: "0900000079" },
    });
    fireEvent.change(within(tab).getByLabelText("Mật khẩu"), {
      target: { value: "mat-khau-bi-mat" },
    });
    fireEvent.click(within(tab).getByRole("button", { name: "Lưu" }));

    expect(await within(tab).findByText("Đã lưu cho số 09••••••79")).toBeInTheDocument();
    const put = fetch.mock.calls.find(([request]) => request.method === "PUT");
    expect(await put?.[0].json()).toEqual({ phone: "0900000079", password: "mat-khau-bi-mat" });
    expect(within(tab).queryByLabelText("Mật khẩu")).not.toBeInTheDocument();
  });

  it("removes a saved login", async () => {
    const { fetch } = renderSetup(overview(), {
      "GET /api/logins/0": reply(SAVED),
      "DELETE /api/logins/0": reply(null, 204),
    });
    const tab = await setupTab();

    fireEvent.click(await within(tab).findByRole("button", { name: "Xóa" }));

    expect(await within(tab).findByLabelText("Mật khẩu")).toHaveValue("");
    expect(requestsTo(fetch, "DELETE /api/logins/0")).toBe(1);
  });

  it("says so when Windows did not keep it", async () => {
    renderSetup(overview(), {
      "GET /api/logins/0": reply(NONE),
      "PUT /api/logins/0": reply({ error: "credentials", detail: "error 1312" }, 503),
    });
    const tab = await setupTab();

    fireEvent.change(await within(tab).findByLabelText("Số điện thoại"), {
      target: { value: "0900000079" },
    });
    fireEvent.change(within(tab).getByLabelText("Mật khẩu"), { target: { value: "x" } });
    fireEvent.click(within(tab).getByRole("button", { name: "Lưu" }));

    expect(await within(tab).findByRole("alert")).toHaveTextContent("Chưa lưu được");
  });
});

describe("SetupTab without auto setup", () => {
  it("has no button: the runs and the daily switch set up MuMu and waking", async () => {
    renderSetup();

    const tab = await setupTab();
    expect(
      within(tab).queryByRole("button", { name: "Thiết lập tự động" }),
    ).not.toBeInTheDocument();
    expect(within(tab).queryByText("Court Booker làm thay bạn")).not.toBeInTheDocument();
  });
});

describe("SetupTab guide", () => {
  it("holds no notification switch: it is on the ticket", async () => {
    renderSetup();
    const tab = await setupTab();

    expect(within(tab).queryByRole("switch")).not.toBeInTheDocument();
  });

  it("opens a guide row on a press", async () => {
    renderSetup();
    const tab = await setupTab();
    const morning = within(tab).getByText("Mỗi sáng diễn ra thế nào").closest("details");
    expect(morning).not.toHaveAttribute("open");

    fireEvent.click(within(tab).getByText("Mỗi sáng diễn ra thế nào"));

    expect(morning).toHaveAttribute("open");
    expect(morning).toHaveTextContent(
      "05:50 máy tự thức dậy, mở MuMu và app Vinhomes. 06:00 đặt các khung đã chọn",
    );
    const trouble = within(tab).getByText("Khi có sự cố").closest("details");
    expect(trouble).toHaveTextContent('Báo "Hết chỗ"Khung đó có người đặt trước.');
  });
});
