# Đưa TĐH Chemistry lên Internet (Render)

Mục tiêu: website chạy 24/7 tại một địa chỉ `https://…onrender.com` (hoặc tên miền riêng), học sinh vào được từ nhà, không cần bật máy Mac.

## Vì sao chọn Render

- Máy chủ được quản lí sẵn: tự cấp HTTPS, tự khởi động lại khi lỗi, không phải tự cập nhật hệ điều hành như thuê VPS.
- Có khu vực **Singapore**, gần Việt Nam.
- Có đĩa lưu bền cho cơ sở dữ liệu, tự chụp bản sao (snapshot) hằng ngày.

**Chi phí (theo bảng giá Render, tháng 11/2026):** gói máy chủ 0.5 CPU / 512 MB là 7 USD/tháng, đĩa 1 GB là 0,25 USD/tháng, gói workspace Hobby 0 USD. Tổng khoảng **7,25 USD/tháng**, tính theo giây, huỷ lúc nào cũng được.

## Đã chuẩn bị sẵn trong thư mục này

| Tệp | Vai trò |
|---|---|
| `render.yaml` | Bản thiết kế: Render đọc tệp này và tự tạo máy chủ ở Singapore, gắn đĩa 1 GB, đặt các biến cấu hình |
| `wsgi.py`, `requirements.txt` | Chạy website bằng gunicorn (máy chủ web dùng cho môi trường thật) |
| `.gitignore` | Chặn thư mục `data/` (dữ liệu thật, mật khẩu ban đầu) khỏi bị đưa lên kho mã |

Trên máy chủ thật, website tự bật: cookie chỉ gửi qua HTTPS, HSTS, không tạo dữ liệu demo, giờ Việt Nam, mật khẩu ban đầu do Render sinh ngẫu nhiên.

## Các bước

### Phần thầy/cô tự làm (cần tài khoản và thẻ của thầy/cô)

1. **GitHub** — vào <https://github.com>, đăng kí hoặc đăng nhập. Bấm **New repository**, đặt tên `tdh-chemistry`, chọn **Private**, không tích thêm gì, bấm **Create repository**. Chép địa chỉ kho (dạng `github.com/ten-cua-thay-co/tdh-chemistry`).
2. **Render** — vào <https://dashboard.render.com/register>, chọn đăng nhập bằng GitHub. Vào **Billing** thêm thẻ thanh toán (gói 7 USD/tháng cần thẻ).
3. Báo lại cho Claude địa chỉ kho GitHub.

### Phần Claude làm tiếp cùng thầy/cô

4. Tạo một khoá riêng cho kho này (deploy key) để đẩy mã nguồn lên GitHub; thầy/cô dán khoá công khai vào **Settings → Deploy keys** của kho (tích *Allow write access*).
5. Đẩy mã nguồn lên GitHub.
6. Trên Render: **New → Blueprint → chọn kho `tdh-chemistry` → Apply**. Render dựng máy chủ trong vài phút.
7. Lấy mật khẩu ban đầu: Render → dịch vụ `tdh-chemistry` → **Environment** → `TDH_ADMIN_PASSWORD`. Đăng nhập tài khoản `giaovien`, hệ thống bắt đổi mật khẩu ngay.
8. Kiểm tra trên địa chỉ thật: đăng nhập, tạo lớp, làm thử một đề bằng điện thoại.

## Sau khi đã chạy

- **Sao lưu:** đăng nhập tài khoản quản trị → **Nhật kí và sao lưu** → *Tải bản sao lưu (.db)*. Nên tải mỗi tuần. Render cũng tự chụp đĩa hằng ngày.
- **Cập nhật website:** mỗi lần mã nguồn mới được đẩy lên GitHub, Render tự dựng lại. Website gián đoạn vài giây trong lúc đổi phiên bản — tránh cập nhật khi học sinh đang làm bài.
- **Tên miền riêng** (ví dụ `hoa.tenmien.vn`): Render → Settings → Custom Domains, rồi trỏ bản ghi DNS theo hướng dẫn. Không bắt buộc.
- **Chuyển dữ liệu từ máy Mac lên:** máy chủ bắt đầu với cơ sở dữ liệu trống (chỉ có tài khoản `giaovien`). Ngân hàng câu hỏi đã soạn trên máy có thể chuyển lên sau — báo Claude khi cần.
- **Dừng hẳn:** Render → Settings → Delete Web Service (xoá cả đĩa dữ liệu, nhớ tải bản sao lưu trước).

## Trước khi cho lớp thật dùng

1. Hỏi quy định của nhà trường về việc lưu dữ liệu học sinh trên máy chủ ở nước ngoài (Singapore).
2. Chỉ nhập họ tên và lớp; không nhập CCCD, địa chỉ, số điện thoại.
3. Thử trước với 5–10 tài khoản trong một buổi kiểm tra không lấy điểm.
4. Tài khoản GitHub và Render nên bật xác thực hai lớp.

## Nếu sau này muốn chuyển sang VPS

Mã nguồn không phụ thuộc Render: máy chủ nào có Python 3.10 trở lên đều chạy được bằng đúng lệnh trong `render.yaml`
(`gunicorn wsgi:application …`), đặt sau một proxy có HTTPS như Caddy. Dữ liệu chuyển bằng tệp sao lưu `.db`.
