"""Notification tests with a fake PowerShell; no toast."""

import base64
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from court_booker.notify import (
    REASONS,
    court_name,
    failure_reason,
    format_notification,
    format_quota_warning,
    format_ticket_caption,
    format_zalo_report,
    format_zalo_test,
    send_windows,
)
from court_booker.runner import RoundResult

RESULTS = [
    RoundResult("18:00 - 19:00", True, "booked", 4.2),
    RoundResult("19:00 - 20:00", False, "Slot 19:00 - 20:00 is fully booked", 2.1),
]


TARGET = date(2026, 10, 26)
COURT = "S6 - Sân tennis"


def notification(results, error=None, language="vi", dry_run=False, interrupted=False):
    return format_notification(
        results,
        error,
        dry_run=dry_run,
        interrupted=interrupted,
        target=TARGET,
        court=COURT,
        language=language,
    )


def test_notification_has_a_line_per_round_in_vietnamese():
    title, body = notification(RESULTS)

    assert title == "Đặt sân 26/10: 1/2 thành công"
    assert body.splitlines() == ["✅ 18:00 - 19:00 · S6", "❌ 19:00 - 20:00 · Hết chỗ"]


@pytest.mark.parametrize(
    ("language", "line"),
    [
        ("vi", "🔧 Đã tự sửa 2 lỗi khi chuẩn bị"),
        ("en", "🔧 Repaired 2 problem(s) while getting ready"),
    ],
)
def test_notification_counts_the_repairs_made_while_getting_ready(language, line):
    _, body = format_notification(
        RESULTS,
        None,
        dry_run=False,
        interrupted=False,
        target=TARGET,
        court=COURT,
        language=language,
        repairs=2,
    )

    assert body.splitlines()[-1] == line


def test_notification_without_repairs_says_nothing_of_them():
    _, body = notification(RESULTS)

    assert "🔧" not in body


def test_notification_in_english():
    title, body = notification(RESULTS, language="en")

    assert title == "Courts for 26 Oct: 1/2 booked"
    assert body.splitlines() == ["✅ 18:00 - 19:00 · S6", "❌ 19:00 - 20:00 · Fully booked"]


def test_notification_names_the_court_the_app_booked():
    booked = [RoundResult("18:00 - 19:00", True, "booked", 4.2, court="S9 - Sân tennis")]

    assert notification(booked)[1] == "✅ 18:00 - 19:00 · S9"


@pytest.mark.parametrize(
    ("language", "warning"),
    [
        ("vi", "⚠️ Tài khoản thuộc BS, sân S6 không thuộc phân khu này"),
        ("en", "⚠️ The account is in BS; court S6 is not"),
    ],
)
def test_notification_warns_of_a_court_outside_the_account(language, warning):
    body = format_notification(
        RESULTS,
        None,
        dry_run=False,
        interrupted=False,
        target=TARGET,
        court=COURT,
        language=language,
        account="bs",
    )[1]

    assert body.splitlines()[-1] == warning


@pytest.mark.parametrize("account", ["origami", None, "khu-b"])
def test_notification_says_nothing_of_a_matching_or_unknown_account(account):
    body = format_notification(
        RESULTS,
        None,
        dry_run=False,
        interrupted=False,
        target=TARGET,
        court=COURT,
        account=account,
    )[1]

    assert len(body.splitlines()) == len(RESULTS)


def test_notification_of_a_dry_run_says_so():
    passed = [RoundResult("18:00 - 19:00", True, "dry run passed", 3.0)]

    assert notification(passed, dry_run=True)[0] == "Đặt sân 26/10: 1/1 thành công (chạy thử)"
    assert notification(passed, dry_run=True, language="en")[0].endswith(": 1/1 booked (dry run)")


def test_each_instance_of_a_run_with_several_names_itself():
    title, _ = format_notification(
        RESULTS, None, dry_run=True, interrupted=False, target=TARGET, court=COURT, instance=1
    )

    assert title == "MuMu 1 · Đặt sân 26/10: 1/2 thành công (chạy thử)"


def test_a_run_that_failed_before_its_rounds_gives_its_reason():
    error = "Another run is in progress (dry_run, pid 42)"

    assert notification([], error) == ("Đặt sân 26/10: không đặt được", "Đang có lần chạy khác")
    assert notification([], "MuMu did not start", language="en") == (
        "Courts for 26 Oct: not booked",
        "Error, see the activity log",
    )


def test_a_stopped_run_lists_its_finished_rounds():
    title, body = notification(RESULTS[:1], "interrupted", interrupted=True)

    assert title == "Đặt sân 26/10: đã dừng"
    assert body == "✅ 18:00 - 19:00 · S6"
    assert notification([], "interrupted", interrupted=True) == ("Đặt sân 26/10: đã dừng", "")


def test_an_unknown_language_falls_back_to_vietnamese():
    assert notification(RESULTS, language="fr")[0] == "Đặt sân 26/10: 1/2 thành công"


@pytest.mark.parametrize(
    ("court", "name"),
    [
        ("S6 - Sân tennis", "S6"),
        ("S10 - Sân tennis", "S10"),
        ("S6 - Sân cầu lông", "S6 cầu lông"),
        ("S9 - Sân Pickleball", "S9 Pickleball"),
        ("S10 - Sân tập bóng rổ 01", "S10 tập bóng rổ 01"),
        ("Sân tennis", "Sân tennis"),
    ],
)
def test_a_court_is_named_short_with_its_sport_unless_tennis(court, name):
    assert court_name(court) == name


@pytest.mark.parametrize(
    ("detail", "vi", "en"),
    [
        ("Slot 19:00 - 20:00 is fully booked", "Hết chỗ", "Fully booked"),
        ("Court S6 - Sân tennis is fully booked", "Sân S6 đã kín", "Court S6 fully booked"),
        (
            "The app refused the booking: Quá số lần\nđặt",
            "App từ chối: Quá số lần\nđặt",
            "The app refused: Quá số lần\nđặt",
        ),
        (
            "Booking quota used up: Căn hộ đã hết hạn mức đăng ký tiện ích cho phép.",
            "Hết hạn mức đặt sân",
            "Booking quota used up",
        ),
        (
            "Skipped: the booking quota is used up",
            "Bỏ qua vì đã hết hạn mức",
            "Skipped: booking quota used up",
        ),
        (
            "Outcome unknown: no ticket 30 s after confirming",
            "Không rõ đã đặt được chưa, xem app Vinhomes",
            "Outcome unknown, check the Vinhomes app",
        ),
        ("Date 26 not open after 12 attempts", "Ngày chưa mở đặt", "Not open for booking yet"),
        (
            "Tapped 'Tiếp tục' but the next screen did not appear",
            "App không chuyển màn hình",
            "The app did not move on",
        ),
        (
            "The app did not show 'Tiện ích'; check that it is logged in",  # before the login
            "App Vinhomes chưa mở được",
            "The Vinhomes app did not open",
        ),
        (
            "The app did not show 'Tiện ích' or 'Utilities' in 180 s; check the app on MuMu 0",
            "App Vinhomes chưa mở được",
            "The Vinhomes app did not open",
        ),
        (
            "The app is logged out (the account logged in on another device): log in again "
            "on MuMu 0, or save the login in the app's setup so a run logs in by itself",
            "App Vinhomes bị đăng xuất, chưa lưu tài khoản để tự đăng nhập",
            "The Vinhomes app is logged out and no login is saved",
        ),
        (
            "The app refused the saved login: Sai mật khẩu. Vui lòng thử lại; save it again in "
            "the app's setup (the app locks an account after 5 wrong passwords)",
            "App từ chối tài khoản đã lưu: Sai mật khẩu. Vui lòng thử lại",
            "The app refused the saved login: Sai mật khẩu. Vui lòng thử lại",
        ),
        (
            "Neither the home screen nor a message showed 30 s after 'Đăng nhập' (3 tap(s)); "
            "check the app",
            "Chưa tự đăng nhập lại được",
            "Could not log in again",
        ),
        (
            "Button not found: 'S6 - Sân tennis'",
            "Có lỗi, xem nhật ký",
            "Error, see the activity log",
        ),
        (None, "Có lỗi, xem nhật ký", "Error, see the activity log"),
    ],
)
def test_failure_reasons_read_as_in_the_app(detail, vi, en):
    assert failure_reason(detail, "vi") == vi
    assert failure_reason(detail, "en") == en


@pytest.mark.parametrize("language", ["vi", "en"])
def test_reasons_match_the_app_translations(language):
    locale = Path(__file__).resolve().parents[1] / "ui" / "src" / "i18n" / "locales"
    reasons = json.loads((locale / f"{language}.json").read_text(encoding="utf-8"))["reasons"]

    assert {key: re.sub(r"\{\{(\w+)\}\}", r"{\1}", text) for key, text in reasons.items()} == (
        REASONS[language]
    )


def completed(returncode=0, stderr=b""):
    return subprocess.CompletedProcess([], returncode, b"", stderr)


def test_send_windows_runs_an_encoded_powershell_script():
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return completed()

    assert send_windows("Đặt sân 26/10: 1/2 thành công", "✅ a\n❌ <b> & 'c'", run=run)
    (command, kwargs), *_ = calls
    assert Path(command[0]).parts[-4:] == (
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
    assert command[1:4] == ["-NoProfile", "-NonInteractive", "-EncodedCommand"]
    script = base64.b64decode(command[4]).decode("utf-16-le")
    assert r"AppUserModelId\CourtBooker'" in script
    assert "-Value 'Court Booker'" in script
    assert "<text>Đặt sân 26/10: 1/2 thành công</text>" in script
    assert "<text>✅ a\n❌ &lt;b&gt; &amp; &apos;c&apos;</text>" in script
    assert "CreateToastNotifier('CourtBooker')" in script
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] > 0


def test_a_title_cannot_end_the_scripts_here_string():
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return completed()

    send_windows("x\n'@\nRemove-Item C:\\", "", run=run)

    script = base64.b64decode(calls[0][4]).decode("utf-16-le")
    assert "\n'@\n" not in script.split("$xml.LoadXml(@'", 1)[1].split("\n'@)", 1)[0]


@pytest.mark.parametrize(
    "outcome",
    [
        completed(1, b"#< CLIXML\nToast failed"),
        OSError("powershell.exe not found"),
        subprocess.TimeoutExpired("powershell.exe", 20),
    ],
)
def test_a_notification_failure_is_logged_not_raised(outcome, caplog):
    def run(command, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    assert send_windows("title", "body", run=run) is False
    assert "Windows notification not shown" in caplog.text


def test_send_windows_does_nothing_outside_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    assert send_windows("title", "body") is False


@pytest.mark.parametrize(
    ("language", "title", "body"),
    [
        (
            "vi",
            "MuMu 1 · Lần đặt tới thiếu hạn mức",
            "Nhóm 68 · 09••62: Sân Tennis còn 1/8 của tháng 11/2026, mà đã chọn 2 khung giờ."
            " Đổi tài khoản trong Thiết lập.",
        ),
        (
            "en",
            "MuMu 1 · Next booking short of quota",
            "Nhóm 68 · 09••62: Sân Tennis: 1/8 left in Nov 2026, 2 slots chosen."
            " Choose another account in the Setup.",
        ),
    ],
)
def test_the_quota_warning_names_the_account_and_what_is_left(language, title, body):
    shown = format_quota_warning(
        utility="Sân Tennis",
        month="2026-11",
        left=1,
        limit=8,
        slots=2,
        account="Nhóm 68 · 09••62",
        language=language,
        instance=1,
    )

    assert shown == (title, body)


def test_the_quota_warning_without_an_account_starts_with_the_sport():
    _, body = format_quota_warning(utility="Sân Tennis", month="2026-11", left=0, limit=8, slots=1)

    assert body.startswith("Sân Tennis còn 0/8")


def test_the_quota_warning_names_the_sport_in_its_language():
    def body(language):
        return format_quota_warning(
            utility="Sân Pickleball",
            month="2026-11",
            left=1,
            limit=8,
            slots=2,
            language=language,
            sport="pickleball",
        )[1]

    assert body("en").startswith("Pickleball: 1/8 left in Nov 2026")
    assert body("vi").startswith("Sân Pickleball còn 1/8")


def test_the_zalo_report_names_whose_account_it_booked_with():
    text = format_zalo_report("Đặt sân 30/11: 1/1 thành công", "✅ 17:00 - 18:00 · S6", "An · BON")

    assert text.splitlines() == [
        "Đặt sân 30/11: 1/1 thành công",
        "👤 An · BON",
        "✅ 17:00 - 18:00 · S6",
    ]
    assert format_zalo_report("Title", "line") == "Title\nline"


@pytest.mark.parametrize(
    ("language", "lines"),
    [
        ("vi", ["👤 An · BON", "S6 · 30/11 · 17:00 - 18:00", "Mã vé 1234567"]),
        ("en", ["👤 An · BON", "S6 · 30 Nov · 17:00 - 18:00", "Ticket 1234567"]),
        ("fr", ["👤 An · BON", "S6 · 30/11 · 17:00 - 18:00", "Mã vé 1234567"]),
    ],
)
def test_a_ticket_s_caption_says_whose_and_when(language, lines):
    caption = format_ticket_caption(
        code="1234567",
        court="S6 - Sân tennis",
        play_date=date(2026, 11, 30),
        slot="17:00 - 18:00",
        holder="An · BON",
        language=language,
    )
    assert caption.splitlines() == lines


def test_the_zalo_test_message_is_in_the_saved_language():
    assert format_zalo_test("vi").startswith("Court Booker đã kết nối.")
    assert format_zalo_test("en").startswith("Court Booker is linked.")
