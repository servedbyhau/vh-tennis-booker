# Field notes

What the Vinhomes Resident app and the MuMu emulator do, as measured on the development
machine. The code relies on these facts; the app can change without notice. How the code uses
them: [how-it-works.md](how-it-works.md), [architecture.md](architecture.md).

## Booking flow (app screens)

Home ("Tiện ích") → Utilities list ("Sân Tennis") → Calendar (date, then the slot list; slot;
"Tiếp tục") → venues ("Chọn phân khu", optional) → Court list ("Chọn vị trí/dịch vụ") → Booking
details ("Số lượng cư dân", "Tiếp tục") → Confirmation (consent checkbox, "Xác nhận") → Ticket.
One Back from the ticket returns to the Utilities list, where the next round starts.

- The calendar, venues, court list and details page share the title "Đăng ký tiện ích", so each
  is known by a label of its own (above). The venues and the court list are one page, below
  "Thông tin dịch vụ".
- With a single venue (`'Origami_ Sân tennis'`) the app moves on to the courts by itself within
  a fraction of a second; a read may catch the venues or not, and a read right after the venue
  tap may still show them. A heading can show a read before its entries (8 of 30 reads for the
  venues). The details page's caption shows about 24 reads before its "Tiếp tục" is enabled.
- Back: each screen shows 0.13-0.24 s after Back, at times after an empty frame (the root and
  the status bar only). The status bar's labels change on their own, so they never tell screens
  apart. A notice dialog closes back to the page beneath ("Đóng" or Back). Back on the home
  screen leaves the app.

## Reading the app

- Flutter exposes text in `content-desc`, not `text`, and builds lazily: off-screen elements
  are absent and bounds are clipped to what shows.
- Day label: `2, Thứ Sáu, 2 tháng 10, 2026`. Slot: `09:00 - 10:00`; full: `18:00 - 19:00\nHết
  chỗ`; a full court: `S9 - Sân tennis\nHết chỗ`. 13 slots (06-12, 14-21) fit at 540x1600 without
  scrolling. Bookable: today to today + 2.
- The slot selection is not in the tree. The app takes a tap a few frames later: "Tiếp tục"
  11-40 ms after the slot tap booked the slot selected before, 60-100 ms after it the slot
  tapped (the flow waits 0.1 s). "Tiếp tục" usually shows enabled in the same read as the slot
  list, but once (06:00:10, 2026-10-19) the list showed with it still disabled.
- A month shows only its own days (no days of the next month on its last row), so a date in
  the next month needs the next-month button. The calendar opens on the current month.
- The month buttons, `‹` and `›` right of "Tháng 10 ▾ 2026 ▾", are unlabelled `Button`
  nodes at 540x1600: `‹` [403,162][469,228], `›` [469,162][535,228] (2026-10-25). Both are
  greyed out and not clickable while that month has no bookable day. Enabled, `›` is a
  clickable node labelled "Tháng sau" at the same bounds: seen on the golf calendar, which
  books further ahead (2026-10-27); the flow finds it by that label first. `next_month_xy` and
  `prev_month_xy` tap their middles; the driver clicks the smallest clickable element at the
  point, so a point right of x 469 is the next-month button. The first real switch, on
  30/10 for 1/11, worked (`›` found unlabelled, tapped at its middle).
- Until a day is picked, "Chọn ngày dự kiến sử dụng" ("Select expected date of use") shows
  under the calendar; a tap the app takes removes it within 0.05 s, and the slot list shows
  about 0.8 s later (2026-10-30). The month switched to slides in for about 0.2 s, its days
  moving and not clickable; a tap on a day then only stops the slide: the prompt stayed and no
  slot showed for 30 s, twice in a row at 06:00 on 30/10. The flow taps a day once it is
  clickable, and taps it again while the prompt stays. With that fix, a real run later on
  30/10 booked two slots for 1/11, and the 31/10 06:00 run booked two for 2/11.

## Court list moves under the tap

The court list can show before the "Thông tin dịch vụ" block above it has loaded. Once it loads
("Xem thêm" appears) the whole list moves up 232 px, so a tap placed from the read before lands
two courts lower: a tap at S6's first centre (y=1217) opened S9 (booked by mistake on 13/10 and
17/10). The read just before the tap can show the old layout, so a dump cannot predict it; the
first court is no safer (S10's centre falls on S8 after the move).

The booking details page names the court it opened (a non-clickable label, 0.23-0.45 s after
the tap, before its "Tiếp tục"). The flow checks it there, goes back and taps again; each wrong
court costs about 1.5 s.

## Consent and confirmation

- The consent checkbox has no label: it is the smallest clickable node level with the caption
  `Tôi đã hiểu và đồng ý với ` (seen at `[35,1323][79,1367]`, once shifted to x=43), so it is
  located per run. "Xác nhận" is disabled until it is ticked.
- The app takes the tick a few frames after "Xác nhận" shows enabled: "Xác nhận" 65-79 ms after
  the tick did nothing (the page stayed), 97 ms after it booked (the flow waits 0.2 s).
- Before "Xác nhận" the page names what it books in one label: `Sân Tennis\nThời gian đặt
  lịch\n17/10/2026 15:00 - 16:00\nVị trí/dịch vụ\nS6 - Sân tennis\n...`.
- After "Xác nhận": the page stays about 0.75-1.0 s while the server answers, then a frame
  without any app label, then the ticket or a notice. The empty frame shows on both paths, so
  the page going away proves nothing (a round was logged booked by mistake on 2026-10-14).
- The ticket's title showed 0.66-1.6 s after "Xác nhận" at 06:00, more than 10 s once with a
  slow server at midday.
- "Xác nhận" can be swallowed under load: in 2 of 26 loaded rounds (lag, packet loss, CPU) the
  page stayed unchanged for 30 s and a tap by hand then booked. The page also stays while the
  server answers, so a read cannot tell the two apart. A second tap while the server was still
  answering the first booked the slot once, with no notice.

## Ticket screen

The first read after "Xác nhận" holds the title `Chi tiết đặt lịch` and, at 06:00, often the
status `Đang xử lý` but no time or court yet; later the status `Đã đăng ký`, the codes, time,
court and a clickable `Đặt lịch khác`.

## History page

Read on 2026-11-22 and 23 in Vietnamese, on three accounts (tennis and pickleball); not seen in
English. It opens at any hour (02:12 to 02:43 on 2026-11-23), while the calendar is closed from
21:00 to 06:00.

- The icon at the top right of the utilities list (no label, `[472,42][528,100]`) opens
  `Lịch sử tiện ích`: the account's bookings, newest first, one clickable card each (four on
  the screen). A card's label, line by line: the utility, `Mã đặt: 1234567`,
  `Vị trí: S6 - Sân tennis`, `Thời gian: 03/10/2026 08:00 - 09:00`, `Trạng thái:`, the status
  (`Đã đăng ký`, `Đã huỷ`), `Thời gian tạo: 01/10/2026 - 06:00`. The page has an unlabelled
  filter button where the list has the history icon.
- It goes back far (486 cards read on the three accounts, the oldest of 2025-01-11, no end
  reached) and loads as it is scrolled; a swipe of 0.7 of the height moves it about three cards.
  Cards are in the order they were booked, the play day at most two days later, so a month's
  cards end at the first one booked more than two days before the month.
- The filter button opens a sheet, `Bộ lọc`, of three: `Tên tiện ích` (a long list, with the
  tickets of VinWonders and others; several may be chosen), `Trạng thái tiện ích` (several) and
  `Thời gian đặt tiện ích`, a calendar of **one day of play**, no range. `Đặt lại` clears it, its
  `Xác nhận` applies it at once; opened again, it keeps the statuses, not the day.
- The statuses there: `Đang xử lý`, `Thanh toán thất bại`, `Đã đăng ký`, `Đang sử dụng`,
  `Đã sử dụng`, `Không sử dụng` (the slot passed without its code being scanned), `Đã huỷ`,
  `Chờ hoàn tiền`, `Đã hoàn tiền`, `Từ chối hoàn tiền`. Of the courts, which cost nothing, only
  `Đã đăng ký`, `Đã sử dụng`, `Không sử dụng` and `Đã huỷ` were seen (`Đang xử lý` right after a
  booking).
- **Rain**: the management cancels the ticket the morning after (08:52 and 10:51 on the two days
  seen), so it reads `Đã huỷ` like one the resident cancelled; neither its card nor its page
  tells them apart. The app's notifications (the bell on the home screen) do: "Tiện ích Sân
  Tennis Quý cư dân đăng ký sử dụng ngày 03/10/2026 08:00-09:00 đã bị hủy do Hỗ trợ hoàn lượt do
  trời mưa khung giờ 07:00 - 12:00 ngày 03/10/2026" (made-up day and times).
- Reading a month's cards and returning to the home screen took 5.0-8.7 s (2-4 swipes, 10-18
  cards); two reads in a row gave the same on each of three machines.
- A card opens the ticket, `Chi tiết đặt lịch`, with **`Hủy tiện ích`** at its top right
  (`[376,38][528,104]`, over the place of those icons), an element labelled `qr code`, the
  status, and one element with the details, the booking code on a line of its own. Inside it
  are `Xem thêm` (left) and `Chỉ đường` (right, bottom at 1140), then the fees. Back returns
  to the history page.
- **Cancelling** (2026-11-24, a badminton ticket booked for the test): `Hủy tiện ích` opens a
  dialog titled the same, "Bạn chắc chắn muốn hủy tiện ích?", with `Hủy bỏ` and `Xác nhận`.
  `Xác nhận` shows "Huỷ tiện ích thành công" for about a second over the history page, whose
  card still reads `Đã đăng ký`; the page opened again reads `Đã huỷ`. The cancelled slot's
  quota came back at once (0/8 of badminton read right after). Not seen in English.
- The ticket moves its lower half while its description loads: the place of `Chỉ đường` read
  0.5 s after the ticket showed was 232 px too low by the time of the picture.
- The app does not block screenshots of these pages. Reading the page and two tickets took
  5-6 s, one ticket 4 s. How long after 06:00 a ticket turns from `Đang xử lý` to `Đã đăng ký`
  is not known yet.

## Dialogs

All are titled "Thông báo": the title node spans `[0,33][540,1600]` and holds the message and a
clickable "Đóng"; the page beneath leaves the dump.

- **Closed hours** (a tap on "Sân Tennis" before 06:00 or after 21:00): "Ban quản lý BQL Grand
  Park chỉ nhận đăng ký Sân Tennis từ 06:00 đến 21:00 mỗi ngày". Back closes it and the list
  shows 0.1 s later. The app most likely checks the MuMu clock: on 2026-10-24, with MuMu 0.71 s
  behind NTP time, taps every 0.35 s still opened the calendar at 21:00:00.73 NTP (21:00:00.02
  on MuMu) and got the notice from 21:00:01.14 NTP on, 0.05 s after the tap like the calendar.
  The flow closes it and taps again until `open_retry_seconds`.
- **Quota**: each apartment may book 2 slots a day and 8 a month; once either is used the app
  shows "Căn hộ đã hết hạn mức đăng ký tiện ích cho phép." (the same message for the day and the
  month), usually after the calendar's "Tiếp tục" (0.9 s after the tap, 2026-10-24), once after
  "Xác nhận" (0.72 s after the tap). The flow knows it by `quota_full` ("hết hạn mức") and the run skips the rounds left,
  which book the same day. What counts, from 486 cards of three accounts (2026-11-23, 43
  months of tennis): the tickets of the **month of play**, of that utility alone, but for those
  `Đã huỷ`, whoever cancelled them; `Không sử dụng` counts. No month held more than 8, 26 held
  exactly 8, 18 of those with more tickets cancelled beside them (66 in one month); nine of the
  26 only reach 8 with their unused tickets. By the month of booking two months would hold 9 and
  10. No day held more than 2. One account had 8 of 8 tennis used in November and still booked
  pickleball on 2026-11-21 and 22. Not known: two accounts of one apartment.
- **Slot taken** (someone booked it first): after "Xác nhận", "Tiện ích đã hết chỗ, vui lòng
  chọn vị trí/thời gian khác".

### Logged out

The app logs an account out when it logs in on another device; it has no other session
limit, and no apartment to choose after a login (the user, 2026-11-18).

- At the next start (05:45 on 2026-11-11) the login screen showed, then 2 s later a
  "Thông báo" over it: "Phiên đăng nhập của bạn đã hết hạn. Vui lòng đăng nhập lại.", buttons
  "Đóng" and "Đặt lại"; the login screen leaves the dump while it shows.
- The login screen (read on 2026-11-18 after "Tài khoản" > "Đăng xuất" > "Đồng ý"): title
  "Đăng nhập tài khoản", "VIE" (the language), two `EditText` fields without a label (their
  hints show on the screen only), "Quên mật khẩu", the "Đăng nhập" button and "Đăng ký". The
  phone field `[35,426][505,492]` keeps the last number (its `text`) with a count "10/10"
  inside it; the password field `[35,539][505,605]` is `password` and shows its text as dots.
  "Đăng nhập" is disabled (not clickable) until a password is in.
- Text set with the accessibility action (`ACTION_SET_TEXT`) is taken: a password set that way
  read as `••••••••` and enabled "Đăng nhập" in the next read. Emptied again, the field grew to
  `[35,539][505,632]` with "Sai mật khẩu. Vui lòng thử lại" inside it at the bottom, the
  button disabled: the app's own check, nothing sent (no button was tapped).
- In English: "Login account", "Please enter your information", "Forgot password", "Login",
  "Register", and "Wrong password. Please try again".
- The app locks an account after 5 wrong passwords (the user); what a wrong one answers after
  "Đăng nhập" is not seen, so both a notice and a message in a field end the login.
- Logged in by a run (12:57 on 2026-11-18, MuMu 1 logged out by hand): each field takes its
  text only once tapped (the driver taps it, waits 0.3 s, then sets it; without the tap the
  button stayed disabled). One tap on "Đăng nhập" 0.3 s after it turned enabled; the home
  screen showed 3 s later, then the rounds ran. An earlier try's screen stayed unchanged for
  30 s after the tap while MuMu was freezing, yet the account was logged in afterwards.
- The login screen stays as it was while the server checks the login, its button enabled:
  the home screen showed 7-11 s after the tap (5 logins on 2026-11-22, two with a single tap),
  so a tap repeated sooner sends the password again.
- The home screen may show although the session is over: it came from the app's store after a
  restart, and the notice that the session expired some seconds later (2026-11-22).

### Account tab (2026-11-22)

Read on one account in both languages; the same page with other labels.

- The home screen has two tabs at the bottom, `Trang chủ\nTab 1 trong tổng số 2` and
  `Tài khoản\nTab 2 trong tổng số 2` (`Home\nTab 1 of 2`, `Account\nTab 2 of 2`). Back on the
  account tab stays there; the home tab leads back.
- The account tab shows `<name>\n<phone number>` in one clickable element, the number whole (10
  digits from 0), then the apartment with `Thay đổi` (`Change`), and a list that ends with
  **`Xóa tài khoản`** (`Delete account`) `[0,1288][540,1370]` right above `Đăng xuất`
  (`Log out`) `[35,1418][505,1512]`: it is tapped by its whole label only.
- `Đăng xuất` asks in a dialog of that title: "Bạn có muốn đăng xuất khỏi ứng dụng?",
  `Hủy bỏ`, `Đồng ý` (`Cancel`, `Agree`); Back closes it. The login screen showed 0.8 s after
  `Đồng ý`, the phone number still in its field.
- Reading the number took 2.3 s of getting ready (two taps, and 2 s watching for the popup);
  logging out and in again with the saved login 17 s. No OTP was asked.
- `Ngôn ngữ` (`Language`) offers `Tiếng Việt` and `English`.

### Promotion popup over the home screen

Seen first on 2026-11-17 (an event invitation on both accounts); it failed that 06:00 run, whose
Back presses never closed it. Not a "Thông báo" dialog: a clickable scrim over the whole screen,
an image `[23,540][517,1080]`, an unlabelled clickable X above its right corner
`[481,493][517,529]`, and a clickable caption "Không hiện lại" `[331,1096][517,1140]` with its
unlabelled tick box `[331,1096][375,1140]`. The home screen's labels leave the dump.

- It shows 0.3-0.8 s after the home screen once the app starts (2 restarts, 2026-11-17), so a
  run that read the home screen at 05:45 met it at 05:59. It showed again after each restart
  while the box stayed unticked.
- Its size varies: in a later read the image spanned `[23,103][517,1517]`, the X
  `[481,56][517,92]` and the caption `[331,1533][517,1577]`, so the X is found per read. It can
  show at that large size first and shrink to the small one about a second later: a tap placed
  from the first read then misses the X, so the X is tapped again from a new read.
- Whether ticking "Không hiện lại" before the X keeps it away after a restart is not known: two
  tries on 2026-11-17 ended with MuMu frozen.
- The X closed it within 0.1 s, with the home screen beneath. Back did nothing (8 presses).
  A dry run on the fix closed it at 09:57 on 2026-11-17 and went on to the calendar. With the
  popup left to show during the wait, as at 05:59 that day, the warm-up closed it and was on
  the utilities list 0.47 s later, without a Back.
- The English caption is not seen yet; `app_language.py` guesses "Don't show again".

## Other sports (Origami)

Surveyed 2026-10-26 with an account of the Origami subdivision, app in Vietnamese. The
utilities list ("Danh sách tiện ích", section "Tiện ích Vinhomes Grand Park") holds ten
clickable tiles; eight are courts, booked the same way as tennis (the other two, "Nhà Tập Golf
Vip" and "Nướng BBQ", are out of scope). Only "Sân Tennis" has a capital T. Below the
section, "Tiện ích VinWonders" lists links to the VinWonders parks (out of scope).

### Structure of each utility (2026-10-27)

Every tile walked to its booking details page with a read about every 0.3 s, then Back one
page at a time (a page passed by itself shows again after Back). The app gives no name of the
account's subdivision; it shows the utilities, venues and courts of that subdivision.

| Tile | Supplier caption | Venue page (passed by itself) | Court list | Slots |
|---|---|---|---|---|
| Sân Tennis | BQL Grand Park | Origami_ Sân tennis | 4 courts | 13 x 1 h |
| Sân đa năng | Vinhomes Grand Park | Origami _ Sân đa năng | 3 courts | 13 x 1 h |
| Sân bóng chuyền | BQL Grand Park | Origami _ Sân bóng chuyền hơi | 4 courts | 13 x 1 h |
| Sân bóng bàn | BQL Grand Park | Sân bóng bàn | one court, passed by itself | 13 x 1 h |
| Sân bóng rổ | BQL Grand Park | Origami _ Sân bóng rổ | 7 courts | 13 x 1 h |
| Sân bóng đá | BQL Grand Park | Sân bóng đá | 2 courts | 13 x 1 h |
| Sân Pickleball | Vinhomes Grand Park | Origami _ Sân Pickleball | one court, passed by itself | 13 x 1 h |
| Sân cầu lông | BQL Grand Park | Origami _ Sân cầu lông | 3 courts | 13 x 1 h |
| Nhà Tập Golf Vip | Vinhomes Grand Park | none (not after Back either) | Golf Số 01 to 10 | 6 x 2 h (07-13, 15-21) |
| Nướng BBQ | BQL Grand Park | BBQ _ CV 36ha _ Zone 2 | BBQ CV Zone 2 - 01 to 07 | 4 x 2 h (10-14, 17-21) |

- Order of pages after the calendar's "Tiếp tục": the page heading (the tile's name and the
  supplier caption, "Thông tin dịch vụ") shows first, then the venue page, then the court
  list or, with one court, the details page. The venue page was never caught on the way in;
  every walk showed it after one Back from the court list or details page.
- Venue names differ in form: "Origami_ " or "Origami _ " before most, none for table tennis
  and football (whose courts carry S5). A single venue is tapped whatever its name; several
  venues are not seen at Origami (BS lists two, below).
- The details page shows the opened court's name, "Phí đặt chỗ 0 VND | Số lượng cư dân | 4"
  and "Tiếp tục" for all eight sports; its service text varies (the multi-purpose page lists
  "Sân sử dụng các tiện ích: Bóng rổ"; football reads "phục vụ" without "riêng").
- Golf and BBQ book further ahead than today + 2: on 27/10 their calendars showed 27-31/10
  and an enabled "Tháng sau" button.

- The calendar is the same for all eight: "Đăng ký tiện ích", the utility's name, today to
  today + 2, "Khung giờ khả dụng", 13 one-hour slots (06-12, 14-21), "| Hết chỗ", "Tiếp tục".
- The quota counts per utility: with the tennis quota used, the quota notice showed after the
  calendar's "Tiếp tục" for tennis only; the other seven went on.
- A page with a single choice passes on to the next by itself, as the tennis venue does
  (above): a venue page with one venue, a court list with one court. It shows for a moment,
  so a read may catch it or not; it stays when the app is slow, and shows after Back. So after
  "Tiếp tục" the first page read may be the venues ("Chọn phân khu"), the court list ("Chọn
  vị trí/dịch vụ") or, for a utility with a single court, its booking details page (its
  name, "Số lượng cư dân", "Tiếp tục"). Seen: table tennis and pickleball went to the details
  page in the survey, and pickleball's list of one court was read in a dry run; the
  multi-purpose courts' single venue ("Origami _ Sân đa năng") was read in a dry run only
  (2026-10-26). The details and confirmation pages are the same as tennis.
- A full court still shows on the list ("| Hết chỗ"), so the lists below are complete. Courts
  are shown as the app lists them for an Origami account, whatever their S prefix.

| Tile | Court list | Courts |
|---|---|---|
| Sân Tennis | list | S10, S6, S8, S9 - Sân tennis |
| Sân đa năng | list | S10, S7, S9 - Sân đa năng |
| Sân bóng chuyền | list | S10 - Sân bóng chuyền hơi 01, S10 - Sân bóng chuyền hơi 02, S8 - Sân bóng chuyền hơi, S9 - Sân bóng chuyền hơi |
| Sân bóng bàn | one court, passes by itself | S5 - Sân tập bóng bàn 03 |
| Sân bóng rổ | list | S10 - Sân bóng rổ nửa sân 03, S10 - Sân tập bóng rổ 01, S6 - Sân bóng rổ tập ném 01, S6 - Sân bóng rổ tập ném 02, S8 - Sân bóng rổ nửa sân, S9 - Sân bóng rổ tập ném 01, S9 - Sân bóng rổ tập ném 02 |
| Sân bóng đá | list | S5 - Sân bóng đá 5, S5 - Sân bóng đá 7 |
| Sân Pickleball | one court, passes by itself | S9 - Sân Pickleball |
| Sân cầu lông | list | S10 - Sân cầu lông, S6 - Sân cầu lông, S8 - Sân Cầu lông |

- In English (2026-10-27) the list is "Utilities list", section "Utilities Vinhomes Grand
  Park", and the eight tiles read "Multi Purpose Yard", "Volleyball", "Pingpong", "Tennis",
  "Basketball", "Football", "Pickleball" and "Badminton" ("Golf house Vip" and "BBQ" out of
  scope). Venues ("Origami _ Sân bóng chuyền hơi") and court names stay in Vietnamese, as for
  tennis; each sport went to "Confirm" in a dry run.
- Court names are not uniform: "S8 - Sân Cầu lông" has a capital C.
- The basketball list has seven courts; the seventh sits at the bottom edge (y 1594-1600 at
  540x1600). It is in the tree, so the driver clicks it by its label without a swipe; until
  the service info above has loaded, the list shows 232 px lower and the last two courts are
  not in the tree yet.
- Each volleyball court row has a child "Chỉ đường" button (x 53-178); a tap in the middle of
  the row still opens the court.

## Subdivision BS

Surveyed 2026-10-27 with an account of the BS subdivision, app in Vietnamese, the same walk
as Origami. Each subdivision shows its own utilities, venues and courts, so each needs its own
survey.

- The utilities list holds eight tiles, in this order: "Sân bóng chuyền", "Sân Tennis", "Sân
  bóng rổ", "Sân bóng đá", "Sân Pickleball", "Sân cầu lông", "Nhà Tập Golf Vip", "Nướng BBQ".
  No "Sân đa năng" and no "Sân bóng bàn". Tile names, captions, the calendar (13 one-hour
  slots, today to today + 2) and the details page read as at Origami.
- **Several venues.** Tennis, basketball and pickleball list two venues, "BE _ …" and "BS _
  …"; this page stays until a venue is tapped. A venue whose courts are all taken at the slot
  reads "| Hết chỗ" (seen for "BE _ Sân tennis" at 09:00 and 10:00).
- After a single court passes by itself to its details page, one Back shows that court's list
  (one entry), not the venues.

| Tile | Venue | Courts |
|---|---|---|
| Sân bóng chuyền | BS _ Sân bóng chuyền hơi | BCX3 - Sân bóng chuyền hơi 01, BCX3 - Sân bóng chuyền hơi 02 |
| Sân Tennis | BE _ Sân tennis | BE7 - Sân tennis (one, passes by itself) |
| | BS _ Sân tennis | BCX3 - Sân tennis 01, BCX3 - Sân tennis 02, CX2 - Sân tennis 01, CX2 - Sân tennis 02 |
| Sân bóng rổ | BE _ Sân bóng rổ | BE7 - Sân bóng rổ tập ném 01, BE7 - Sân bóng rổ tập ném 02 |
| | BS _ Sân bóng rổ | BCX3 - Sân bóng rổ tập ném 01, BCX3 - Sân bóng rổ tập ném 02 |
| Sân bóng đá | BS _ Sân bóng đá | BCX3 - Sân bóng đá (one, passes by itself) |
| Sân Pickleball | BE _ Sân Pickleball | BE7 - Sân Pickleball (one, passes by itself) |
| | BS _ Sân Pickleball | BCX3 - Sân đa năng (Cầu lông-Pickleball) (one, passes by itself) |
| Sân cầu lông | BS _ Sân cầu lông | BCX3 - Sân cầu lông 01 (one, passes by itself) |
| Nhà Tập Golf Vip | none | Golf Số 01 to 10, as at Origami |
| Nướng BBQ | BBQ _ CV 36ha _ Zone 2 | BBQ CV Zone 2 - 01 to 07, as at Origami |

- The court's venue is not in the court's name in a way the code can rely on (BCX3 and CX2
  courts are both under "BS _"), so `catalog.py` lists each court under its venue, and the
  run taps that venue.
- At 06:00 on 2026-11-01, the BS account selected "BS _ Sân tennis", tapped
  "BCX3 - Sân tennis 01", and reached the ticket for each of two real bookings for 3/11.

## App in English

Set in the app; every screen keeps its layout and order, only the labels differ. Court names,
slots and the booked date and time read the same.

| `Labels` field | Vietnamese | English |
|---|---|---|
| `home` | Tiện ích | Utilities |
| `utility` | Sân Tennis | Tennis |
| `continue` | Tiếp tục | Next |
| `fully_booked` | Hết chỗ | Full |
| `venue_list` | Chọn phân khu | Select subdivision |
| `court_list` | Chọn vị trí/dịch vụ | Select place/service |
| `residents` | Số lượng cư dân | Number of residents |
| `agree` | Tôi đã hiểu (caption `Tôi đã hiểu và đồng ý với `) | I have read (caption `I have read, understood, and agree to `) |
| `confirm` | Xác nhận | Confirm |
| `confirm_page` | Xác nhận đăng ký | Confirm registration |
| `booked_time` | Thời gian đặt lịch | Schedule time |
| `booked_place` | Vị trí/dịch vụ | Place/service |
| `ticket` | Chi tiết đặt lịch | Booking details |
| `processing` | Đang xử lý | Processing |
| `registered` | Đã đăng ký | Registered |
| `notice` | Thông báo | Notification |
| `quota_full` | hết hạn mức | registration quota (seen in a dry run, 2026-10-25) |
| `dont_show_again` | Không hiện lại | Don't show again (a guess, not seen) |
| `home_tab` | Trang chủ | Home (2026-11-22) |
| `account_tab` | Tài khoản | Account (2026-11-22) |
| `log_out` | Đăng xuất | Log out (2026-11-22) |
| `log_out_yes` | Đồng ý | Agree (2026-11-22) |
| `login` | Đăng nhập | Login (2026-11-18) |
| (dialog button) | Đóng | Close |

- A day reads `21, Wednesday, October 21, 2026`.
- Quota notice: "The apartment has reached the allowed utility registration quota."
  Closed hours: "The BQL Grand Park Management Board only accepts Tennis registration from
  06:00 to 21:00 everyday".
- Whole labels tell the languages apart: "Tennis" is clickable only on the utilities list, and
  "Registered" is not the "Registered information" heading of a loading ticket.

## Emulator (MuMu)

- Screen: custom resolution **540x1600**, 220 DPI. In tablet mode `window_size()` reports the
  landscape size, so the screen size is read from the dump; no stored coordinates.
  `MuMuManager setting` reads and writes it while the instance is off; a running instance
  applies a new screen only after a restart, so each run sets it before starting MuMu.
- A screen read (dump) costs 60-75 ms with uiautomator2, 13 ms with the driver (8-31 ms; parsing
  1.2 ms). A uiautomator2 `click(x, y)` holds the touch about 100 ms (151-165 ms a tap); touch
  down + up takes 83-91 ms and the app takes every such tap.
- The MuMu clock follows the PC clock (+15 ms). One NTP answer can be off by half its round trip
  (a 0.57 s check read 0.12 s wrong). Windows Time sets the PC clock on its own schedule: at
  05:50:21 on 2026-10-19, after the run had measured it 0.757 s slow, so a wait on the PC clock
  tapped up to 0.76 s early. The run waits on `perf_counter` instead.
- MuMu can freeze (twice on 2026-10-13 in dry runs, around the court list): device calls hang,
  and `MuMuManager control shutdown` answers but does nothing; `MuMuNxDevice` must be ended by
  hand. A running MuMu shuts down with it within 18 s and starts again in about 24 s (42-48 s
  when the run starts it from cold).
- Each instance runs in its own `MuMuNxDevice.exe --vm MuMuPlayerGlobal-15.0-<index>`; `info`
  of a running instance gives its `pid`, `player_state` (`start_finished`) and
  `is_process_started` (survey of 2026-11-19, instance 0). A freeze made by suspending that
  process: `adb shell echo` gave no answer in 15 s, and **`MuMuManager info` hung too**, so
  MuMuManager is no use while an instance is frozen. Ending the process (`taskkill /F`) let
  `info` answer again within 3 s (`is_process_started: false`); a launch then booted Android
  in 22 s and adb answered. Without a freeze: `control shutdown` stopped it in 4 s, ending the
  process in 0.8 s, and a launch after either booted in 21-24 s. After a shutdown, `adb
  devices` keeps the serial as `offline` until it is disconnected.
- A hung Android (2026-11-19, instance 0, after the driver was force-stopped twice in tests):
  `adb shell echo` answered in 0.5 s, but `am get-current-user` and every `pm` and `am`
  command hung, so the driver could not start; MuMuManager `info` still answered
  (`start_finished`). A working instance answers `am get-current-user` (`0`) in 50-220 ms,
  so that is the run's ping. Ending the instance's process and launching it again had it
  ready on the home screen 41 s after the ping gave up.
- A MuMuManager command can fail at once for no lasting reason: at 05:45:05 on 2026-11-19
  `control launch -v 0` exited with 4294966796 and printed `{"errcode": -500, "errmsg":
  "nemu-api init failed"}` within 0.7 s, while instance 1's process was starting its own
  MuMu (its launch, 0.3 s later, worked). The two launches had overlapped the same way on
  2026-11-15 to 18 without a failure. Another try is the fix (`emulator.CALL_ATTEMPTS`).
- A second instance for a second account (2026-10-25): `MuMuManager clone -v 0`, with
  instance 0 off, copies its disk (5.4 GB, about 70 s) with the app, the driver and the screen
  settings. The command prints `-502 mainnx request failed` after 10 s while MuMu's main process
  finishes the copy (`MPCopyEmulator code=0` in `%APPDATA%\Netease\MuMuPlayerGlobal\logs\nx_main.log`).
  The clone gets its own `android_id` and MAC address and ADB port 16416 (instance 0: 16384).
  Both boot side by side in about 35 s. The clone holds instance 0's app session: its app data
  was cleared (`pm clear com.vinhomes.resident`) before the app ever opened there, then the
  second account logged in, and instance 0 stayed logged in.
- `court-booker new-machine` (2026-11-25): the same copy of 6.8 GB took 78 s, the command again
  answering -502 after 13 s; the copy got its own IMEI and phone model (Galaxy S21 Ultra beside
  instance 0's Galaxy A55), the settings copied, and booted in 29 s with the app. Earlier, with
  MuMu's main process running for two days, the copy stayed an empty instance (`disk_size_bytes`
  0) and `delete` answered `not handle cmd`, until `MuMuManager main close` and `main launch`
  started that process again; the empty instance was then deleted.
- Two instances side by side (timed dry run, 2026-10-25 04:01, one process each): both booted
  from cold in 23-26 s, connected the driver in 4-5 s and were ready on the home screen in
  6 s, as one alone; both tapped the utility 0.06 s after the start, and both retapped through
  the closed-hours notice at the same pace (43-44 times in 5 s).
- Three instances side by side (2026-11-21, i7-8750H with 12 threads and 16 GB, each
  instance custom 4 cores and 3 GB, a third cloned from instance 0 on ADB port 16448):
  with nothing else open they booked 3/3 for real in 4.8-6.0 s a round, ready 46 s after
  a cold start. With VS Code and other apps open, free RAM fell to 0.5 GB while booking,
  CPU stayed at 89-100% and the rounds took 7.6-8.4 s (the court list 3.3-4.6 s after
  "Tiếp tục" instead of 2.4-3.2 s). Three cold starts at once that day (15:21) left 0.8 GB
  free: on all three the driver or Android stopped answering within two minutes, and the runs
  restarted each MuMu.
- Five and six instances side by side (2026-11-23, timed dry runs of one volleyball slot, every
  app closed, 10.5-11.3 GB free before): launched together, all booted in 42-54 s and were
  ready about 1 min 45 s after the launch, but free RAM fell to 0.5 GB while they got ready
  (0.7-2.0 GB while booking). With one core and 2 GB each (six) a round to the confirmation
  page took 7.5-8.0 s and one screen read about 610 ms; with two cores and 2 GB each (five)
  5.2-7.1 s and about 270 ms (three instances with two cores at 06:00: about 190 ms). The PC's
  CPU averaged 23-36% while booking. Android uses 1.1-1.3 GB while booking (MemTotal less
  MemAvailable, three instances of 3 GB each in a dry run, 2026-11-24), so 2 GB is enough.
- **"Hệ thống giới hạn chỉ được đặt một tiện ích trong vòng 60s. Quý khách vui lòng thử lại
  sau"** ("Thông báo", button "Đóng") shows 0.3-0.5 s after the day is selected on the
  calendar (the slot list's query) when more than three machines select it in the same second:
  exactly three get through, in 9 of 9 runs with four to six machines (2026-11-23 and 24, the
  06:00 run of 24/11 among them), and none is stopped with three. The one stopped is mostly the
  last to select the day, but once the second of four was (0.05 s after the first), so the
  order the server gets them in decides. It counts across apartments, devices (each instance
  has its own IMEI and Android id), sports and subdivisions (a BS account with three Origami
  ones, 2026-11-24). It is short despite its text: a stopped machine got through 5-30 s later.
  All the machines share the home network, the likeliest thing counted (not tried: a phone on
  another network). The flow does not know this notice: it looks for the slot for 29 s, then
  closes it and opens the calendar again. Since 2026-11-24 three machines book.
- Two instances booked for real in parallel at 06:00 on 2026-11-01: Origami and BS each
  reached two tickets for 3/11, with every round finishing within 5 s. The one-day BS
  `[[instances]]` entry was removed at 07:05; the daily task still runs instance 0.

## Accessibility agent (refused by the app)

The app refuses to book while any accessibility service is enabled: at "Xác nhận" it shows
"Cảnh báo" ("Thiết bị đang sử dụng ứng dụng không được phép ... Vui lòng tắt quyền
'Accessibility' ...") instead of the ticket; every earlier step works. An on-device agent
(2026-10-18) was dropped for this reason.

## Instrumentation driver

`am instrument` gets UiAutomation, the connection uiautomator2 uses; it is not an accessibility
service (`enabled_accessibility_services` stays `null`) and the app books with it running.

- `am instrument -w` must keep running (its process holds the connection): started with
  `setsid nohup ... &` it outlives the adb shell.
- Only one UiAutomation at a time: a uiautomator2 server must end before the driver starts,
  and uiautomator2 cannot connect while the driver runs.
- The first install takes about 4 s; the driver answers 1.0-1.5 s after `am instrument`.

## App and server timings

- Calendar 0.14 s after "Sân Tennis" (1.3-2.0 s at 06:00, server load), slot list about 2 s
  after the date, court list 1.5-2.5 s after "Tiếp tục", details 0.5 s, confirmation 0.14 s.
- Slow server (2026-10-19, 10:03): court list 4.3 s, details 7.7 s, ticket over 10 s. Nobody
  saw a step take 30 s, busy days included, hence `timeout = 30`.
