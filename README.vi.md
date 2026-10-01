# vh-tennis-booker

> 🇬🇧 [English](README.md)

Dự án học tập về tự động hóa giao diện: điều khiển luồng đặt sân tennis trong app
Android **Flutter** của bên thứ ba (Vinhomes Resident) bằng **Python + uiautomator2**
trên MuMu Player. Không dùng mã nguồn hay API của app, chỉ thao tác trên giao diện.

> [!IMPORTANT]
> **Dự án học tập.** Không liên quan và không được Vinhomes bảo trợ. App phát hiện
> chế độ nhà phát triển (mà ADB bắt buộc phải bật), nên dự án này không dùng để đặt
> sân thật và không chứa cách vượt qua kiểm tra đó. Hãy tôn trọng điều khoản của app
> và các cư dân khác.

## Điểm chính

- **Không ghi cứng tọa độ:** mọi nút được tìm theo chữ lúc chạy, đúng ở mọi độ phân giải.
- **Ô tick không có tên:** tìm phần tử nhỏ bấm được, nằm bên trái và ngang hàng dòng chữ
  "Tôi đã hiểu…"; không bao giờ bấm phần tử khác.
- **Chịu được app lag:** thấy nút là bấm, chờ màn kế tiếp; bấm hụt thì bấm lại.
- **Tự kéo màn hình:** khung giờ nằm dưới được kéo tới khi hiện trọn, không bị nút
  "Tiếp tục" che.
- **Xác nhận kết quả:** chỉ báo thành công khi app đã rời màn "Xác nhận đăng ký".
- **Log có mili-giây** và thời gian từng bước.
- **Mọi chữ trong app nằm ở config.toml:** app đổi chữ thì chỉ sửa file cấu hình.

## Cài đặt và chạy

```bash
git clone https://github.com/HauPham-Wts/vh-tennis-booker.git
cd vh-tennis-booker
pip install -e .
copy config.example.toml config.toml
```

Mở app ở màn hình đầu (thấy "Tiện ích"), rồi:

```bash
court-booker --dry-run
court-booker --slots "18:00 - 19:00" "19:00 - 20:00"
```

Không tìm thấy nút nào đó thì xem cấu trúc màn hình:

```bash
python tools/inspect_screen.py --near "Tôi đã hiểu"
```

Chi tiết kỹ thuật: [docs/how-it-works.md](docs/how-it-works.md).
