# TĐH Chemistry trên Internet

**Địa chỉ website:** <https://tdh-chemistry-x3pu.onrender.com> (chạy 24/7, có HTTPS, không cần bật máy Mac).

| Mục | Giá trị |
|---|---|
| Nơi đặt | Render, khu vực Singapore, dịch vụ `tdh-chemistry-x3pu` |
| Gói | 0.5 CPU / 512 MB (7 USD/tháng) + đĩa 1 GB (0,25 USD/tháng), tính theo giây, bắt đầu từ 14/11/2026 |
| Dữ liệu | Cơ sở dữ liệu SQLite trên đĩa `tdh-data` (gắn tại `/var/data`), Render tự chụp bản sao hằng ngày |
| Mã nguồn | Kho GitHub `tdh-chemistry` (công khai — chỉ chứa mã nguồn và câu hỏi demo, không có dữ liệu hay mật khẩu) |
| Cấu hình | Tệp `render.yaml` trong kho; Render dựng máy chủ theo tệp này |

Máy chủ trên Internet có cơ sở dữ liệu **riêng**, bắt đầu trống (chỉ có tài khoản `giaovien`). Dữ liệu trên máy Mac (`data/`) không tự chuyển lên.

## Đăng nhập lần đầu

1. Vào <https://dashboard.render.com>, bấm dịch vụ **tdh-chemistry-x3pu** → mục **Environment** ở cột trái.
2. Ở dòng `TDH_ADMIN_PASSWORD`, bấm biểu tượng con mắt để hiện giá trị, rồi chép lại.
3. Mở website, đăng nhập mã `giaovien` với mật khẩu đó. Hệ thống bắt đổi mật khẩu ngay; từ đó giá trị trên Render không còn tác dụng.

## Việc thường làm

- **Sao lưu:** đăng nhập tài khoản quản trị → **Nhật kí và sao lưu** → *Tải bản sao lưu (.db)*. Nên tải mỗi tuần và trước mỗi lần cập nhật.
- **Cập nhật website** (khi mã nguồn thay đổi): commit rồi chạy trong thư mục dự án

  ```bash
  git push
  ```

  Render tự dựng lại sau mỗi lần đẩy mã (đã thử ngày 14/11/2026: khoảng 40 giây). Nếu Render không tự dựng, chạy lệnh dưới hoặc vào Render → dịch vụ → **Manual Deploy → Deploy latest commit**:

  ```bash
  ./.tools/render_cli/cli_v2.36.0 deploys create srv-dbs8go8ae00c73csl2l0 --wait --confirm
  ```

  Website gián đoạn vài giây khi đổi phiên bản; dữ liệu trên đĩa được giữ nguyên (đã kiểm chứng qua một lần dựng lại). Tránh cập nhật lúc học sinh đang làm bài.
- **Xem nhật kí máy chủ:** Render → dịch vụ → **Logs**.
- **Tên miền riêng:** Render → dịch vụ → **Settings → Custom Domains**, rồi trỏ DNS theo hướng dẫn.
- **Dừng hẳn và ngừng tính phí:** Render → dịch vụ → **Settings → Delete Web Service**. Thao tác này xoá cả đĩa dữ liệu — tải bản sao lưu trước.

## Công cụ đã cài trên máy Mac (trong `.tools/`, không nằm trong kho mã)

- `gh` (GitHub CLI 2.104.0) — đã đăng nhập tài khoản GitHub của thầy/cô, dùng để đẩy mã lên kho.
- `render` (Render CLI 2.36.0) — đã đăng nhập Render, dùng để xem trạng thái, nhật kí và kích hoạt cập nhật.

Muốn thu hồi quyền của hai công cụ này: GitHub → Settings → Applications → Authorized OAuth Apps → *GitHub CLI* → Revoke; Render → Account Settings → API Keys / CLI tokens → xoá.

## Trước khi cho lớp thật dùng

1. Hỏi quy định của nhà trường về việc lưu dữ liệu học sinh trên máy chủ ở nước ngoài (Singapore).
2. Chỉ nhập họ tên và lớp; không nhập CCCD, địa chỉ, số điện thoại.
3. Thử trước với 5–10 tài khoản trong một buổi kiểm tra không lấy điểm.
4. Bật xác thực hai lớp cho tài khoản GitHub và Render.

## Ghi chú kĩ thuật

- Kho mã để công khai vì Render không đọc được kho khi ở chế độ riêng tư (kết nối GitHub–Render chưa thông). Muốn đổi lại riêng tư, cần nối được tài khoản GitHub trong Render (Account Settings → Git Deployment Credentials) rồi mới đổi, nếu không Render sẽ không lấy được mã mới.
- Mã nguồn không phụ thuộc Render: máy chủ nào có Python 3.10 trở lên đều chạy được bằng lệnh trong `render.yaml` (`gunicorn wsgi:application …`), đặt sau proxy có HTTPS. Dữ liệu chuyển bằng tệp sao lưu `.db`.
