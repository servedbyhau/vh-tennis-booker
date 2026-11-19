import { act, renderHook } from "@testing-library/react";
import { useTranslation } from "react-i18next";
import { describe, expect, it } from "vitest";
import i18n from "./i18n";
import { failureReason } from "./reasons";
import { useFormat } from "./useFormat";

async function reasonOf(reason: string | null, language: "vi" | "en" = "vi") {
  await act(() => i18n.changeLanguage(language));
  const { result } = renderHook(() => ({ t: useTranslation().t, f: useFormat() }));
  return failureReason(result.current.t, result.current.f, reason);
}

describe("failureReason", () => {
  // The reasons as the engine writes them (flow.py, runner.py, cli.py), seen in real runs.
  it.each([
    ["Slot 18:00 - 19:00 is fully booked", "Hết chỗ"],
    ["Court S6 - Sân tennis is fully booked", "Sân Tennis S6 đã kín"],
    [
      "The app refused the booking: Căn hộ đã hết hạn mức đăng ký tiện ích cho phép.",
      "App từ chối: Căn hộ đã hết hạn mức đăng ký tiện ích cho phép.",
    ],
    [
      "Booking quota used up: Căn hộ đã hết hạn mức đăng ký tiện ích cho phép.",
      "Hết hạn mức đặt sân",
    ],
    ["Skipped: the booking quota is used up", "Bỏ qua vì đã hết hạn mức"],
    [
      "Outcome unknown: neither the ticket nor a notice showed 10 s after confirming; " +
        "check the app",
      "Không rõ đã đặt được chưa, xem app Vinhomes",
    ],
    [
      "2026-10-17 18:00 - 19:00 not open after 3 attempt(s): Date 2026-10-17 is not bookable",
      "Ngày chưa mở đặt",
    ],
    ["Tapped 'Tiếp tục' but the next screen did not appear", "App không chuyển màn hình"],
    ["Another run is in progress: dry_run run (pid 17156) since 11:12:48", "Đang có lần chạy khác"],
    [
      "The app did not show 'Trang chủ' or 'Sân Tennis' in 60 s; check that it is logged in",
      "App Vinhomes chưa mở được",
    ],
    [
      "The app did not show 'Tiện ích', 'Sân Tennis', 'Utilities' or 'Tennis' in 180 s; " +
        "check the app on MuMu 1",
      "App Vinhomes chưa mở được",
    ],
    [
      "com.vinhomes.resident is not installed on 127.0.0.1:16384; install it",
      "App Vinhomes chưa được cài trên MuMu",
    ],
    [
      "The app is logged out (the account logged in on another device): log in again on MuMu " +
        "1, or save the login in the app's setup so a run logs in by itself",
      "App Vinhomes bị đăng xuất, chưa lưu tài khoản để tự đăng nhập",
    ],
    [
      "The app refused the saved login: Sai mật khẩu. Vui lòng thử lại; save it again in the " +
        "app's setup (the app locks an account after 5 wrong passwords)",
      "App từ chối tài khoản đã lưu: Sai mật khẩu. Vui lòng thử lại",
    ],
    ["'Đăng nhập' stayed disabled after typing the login", "Chưa tự đăng nhập lại được"],
    [
      "Neither the home screen nor a message showed 30 s after 'Đăng nhập' (3 tap(s)); " +
        "check the app",
      "Chưa tự đăng nhập lại được",
    ],
    ["The app logged out again right after the saved login", "Chưa tự đăng nhập lại được"],
    ["AdbShellError(AdbTimeout('adb read timeout'))", "Có lỗi, xem nhật ký"],
    [null, "Có lỗi, xem nhật ký"],
  ])("words %j as %j", async (reason, words) => {
    expect(await reasonOf(reason)).toBe(words);
  });

  it("words the reasons in English", async () => {
    expect(await reasonOf("Slot 18:00 - 19:00 is fully booked", "en")).toBe("Fully booked");
    expect(await reasonOf("Court S6 - Sân tennis is fully booked", "en")).toBe(
      "Court Tennis S6 fully booked",
    );
  });
});
