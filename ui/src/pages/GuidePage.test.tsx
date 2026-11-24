import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { STORAGE_KEY } from "../manualSteps";
import { paths } from "../paths";
import { renderApp } from "../test/app";
import { reply, requestsTo } from "../test/backend";
import { overview } from "../test/overview";
import { settings } from "../test/settings";

const SECOND = {
  mumu_index: 1,
  slots: ["20:00 - 21:00"],
  subdivision: "",
  sport: "tennis",
  court: "S9 - Sân tennis",
  venue_keyword: "Origami",
  days: [],
};

function openGuide(saved = settings({ instances: [SECOND] })) {
  return renderApp(paths.guide, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(saved),
  });
}

/** The table of what to do, once the machines are known. */
async function table() {
  await screen.findByRole("columnheader", { name: /^Máy 3/ });
  return within(screen.getByRole("region", { name: "Chuẩn bị" }));
}

function pages() {
  return within(screen.getByRole("navigation", { name: "Trang" }));
}

describe("GuidePage", () => {
  it("is a page of its own in the header, with the tasks left", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mumu: true, app: true, login: false }));
    openGuide(settings());
    const link = await pages().findByRole("link", { name: "Hướng dẫn, còn 1 việc" });
    expect(link).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { level: 1, name: "Hướng dẫn" })).toBeInTheDocument();
  });

  it("starts with how to use it, in three steps", async () => {
    openGuide();
    const start = await screen.findByRole("region", {
      name: "Court Booker đặt sân thay bạn lúc 06:00 mỗi sáng, kể cả khi bạn ngủ",
    });
    expect(
      within(start)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([
      "1Làm các việc chuẩn bị bên dưới, một lần.",
      "2Ở trang Đặt sân, chọn tài khoản, môn, sân và khung giờ cho từng máy.",
      '3Bấm "Chạy thử", đạt thì bật "Tự đặt".',
    ]);
  });

  it("says what happens every morning and what to do about problems", async () => {
    openGuide();
    const morning = await screen.findByRole("region", { name: "Mỗi sáng" });
    // The times of the settings, once known.
    await within(morning).findByText("05:50");
    expect(morning).toHaveTextContent("05:50Máy tự thức dậy, mở MuMu và app Vinhomes.");
    expect(morning).toHaveTextContent("06:00Đặt các khung đã chọn");
    expect(screen.getByRole("region", { name: "Khi có sự cố" })).toHaveTextContent(
      'Báo "Hết chỗ"Khung đó có người đặt trước.',
    );
  });

  it("shows without the backend too", () => {
    renderApp(paths.guide, {});
    expect(screen.getByRole("region", { name: "Mỗi sáng" })).toHaveTextContent("05:45");
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    openGuide();
    expect(await screen.findByRole("region", { name: "Getting ready" })).toBeVisible();
    expect(screen.getByRole("link", { name: /^Guide/ })).toBeVisible();
    await i18n.changeLanguage("vi");
  });
});

describe("GuidePage tasks", () => {
  it("has one tick for MuMu, and one a machine for the rest", async () => {
    openGuide();
    const tasks = await table();
    expect(tasks.getAllByRole("checkbox").map((box) => box.getAttribute("aria-label"))).toEqual([
      "Đã cài MuMu Player",
      "Đã cài app Vinhomes Resident trong MuMu, Máy 1",
      "Đã cài app Vinhomes Resident trong MuMu, Máy 2",
      "Đã cài app Vinhomes Resident trong MuMu, Máy 3",
      "Đã đăng nhập app Vinhomes, Máy 1",
      "Đã đăng nhập app Vinhomes, Máy 2",
      "Đã đăng nhập app Vinhomes, Máy 3",
    ]);
    expect(tasks.getByRole("columnheader", { name: /^Máy 3/ })).toHaveTextContent("đang tắt");
    expect(tasks.getByRole("columnheader", { name: "Máy 2" })).toBeVisible();
  });

  it("keeps a tick in the browser, of its machine, and counts down", async () => {
    const { fetch } = openGuide();
    const tasks = await table();
    expect(pages().getByRole("link", { name: "Hướng dẫn, còn 5 việc" })).toBeVisible();
    const box = (name: string) => tasks.getByRole("checkbox", { name });

    fireEvent.click(box("Đã cài MuMu Player"));
    fireEvent.click(box("Đã cài app Vinhomes Resident trong MuMu, Máy 2"));

    expect(box("Đã cài app Vinhomes Resident trong MuMu, Máy 2")).toBeChecked();
    expect(box("Đã cài app Vinhomes Resident trong MuMu, Máy 1")).not.toBeChecked();
    expect(pages().getByRole("link", { name: "Hướng dẫn, còn 3 việc" })).toBeVisible();
    expect(
      within(screen.getByRole("banner")).getByText(/Còn 3 việc chuẩn bị, xem Hướng dẫn/),
    ).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "")).toMatchObject({
      mumu: true,
      app: false,
      machines: { "1": { app: true, login: false } },
    });
    // The app checks none of it.
    expect(requestsTo(fetch, "GET /api/setup")).toBe(0);
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });

  it("leaves a machine switched off uncounted", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mumu: true, app: true, login: true }));
    openGuide(settings());
    await table();
    expect(pages().getByRole("link", { name: "Hướng dẫn" })).toBeVisible();
  });
});
