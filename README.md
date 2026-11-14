# TĐH Chemistry — lớp học Hoá học số

Website quản lí lớp học và kiểm tra trực tuyến môn Hoá học THPT (CTGDPT 2018). Chạy bằng Python 3 có sẵn trên máy Mac, dữ liệu lưu trong SQLite, **không cần cài thêm gì**.

Lấy ý tưởng chức năng từ các nền tảng kiểm tra – LMS phổ biến, nhưng tên, logo, giao diện và mã nguồn là của riêng TĐH Chemistry.

## 1. Mở website

Cách nhanh nhất: bấm đúp vào tệp **`Mo_TDH_Chemistry.command`** trong thư mục này. Cửa sổ Terminal hiện ra và trình duyệt tự mở `http://localhost:8700`.

Hoặc mở Terminal, gõ `cd ` rồi kéo thả thư mục `TDH_CHEMISTRY_WEB` vào cửa sổ Terminal, nhấn Enter, sau đó chạy:

```bash
python3 server.py
```

Dừng website: nhấn `Ctrl + C` trong cửa sổ Terminal (hoặc đóng cửa sổ).

### Đăng nhập lần đầu

Lần chạy đầu tiên, hệ thống tạo cơ sở dữ liệu và ghi tài khoản ban đầu vào tệp **`data/TAI_KHOAN_BAN_DAU.txt`**:

- tài khoản giáo viên (quản trị) `giaovien` — bắt buộc đổi mật khẩu ngay lần đăng nhập đầu;
- ba tài khoản học sinh demo `demo-hs01…03` thuộc lớp `12A-DEMO` để thầy/cô thử vai học sinh.

Sau khi đã đăng nhập và đổi mật khẩu, hãy xoá tệp đó.

### Cho học sinh cùng Wi-Fi truy cập

Bấm đúp **`Mo_cho_hoc_sinh_cung_WiFi.command`** (hoặc `python3 server.py --lan`). Terminal in ra địa chỉ dạng `http://192.168.x.x:8700` để học sinh gõ trên điện thoại. Máy Mac phải bật và không ngủ trong suốt giờ làm bài.

> **Lưu ý bảo mật:** ở chế độ này website chạy bằng `http` (chưa mã hoá), chỉ nên dùng trong mạng Wi-Fi tin cậy và với dữ liệu thử nghiệm. Xem mục 5 trước khi dùng cho lớp thật.

## 2. Có những gì

| Vai trò | Chức năng |
|---|---|
| **Giáo viên** | Tạo lớp, cấp mã đăng nhập + mật khẩu ban đầu cho học sinh, cấp lại mật khẩu, khoá tài khoản |
| | Ngân hàng câu hỏi: 3 dạng (trắc nghiệm 4 phương án, đúng/sai 4 ý, trả lời ngắn), phân theo khối – chương – mức độ Biết/Hiểu/Vận dụng, trạng thái Nháp/Đã duyệt |
| | Nhập nhanh nhiều câu bằng cách dán văn bản (hoặc JSON); câu nhập vào luôn ở trạng thái nháp chờ duyệt |
| | Soạn đề từ ngân hàng hoặc **tạo đề từ ma trận** (chương × mức độ × dạng câu), báo rõ dòng thiếu câu |
| | Đặt giờ mở/đóng, thời gian làm bài, số lượt, đảo phương án/đảo câu, cách hiện điểm và đáp án |
| | Kết quả: phổ điểm, trung bình, trung vị, câu sai nhiều, danh sách chưa làm, xem từng bài, tải bảng điểm CSV (mở bằng Excel) |
| | Bài giảng (liên kết video/PDF/slide + nội dung), lịch học trực tuyến (Meet/Teams/Zoom), thông báo |
| **Học sinh** | Làm bài trên điện thoại/máy tính, tự lưu liên tục, đồng hồ theo máy chủ, hết giờ tự nộp, xem điểm/đáp án theo thiết lập của giáo viên |
| | Xem bài giảng, đánh dấu đã học, xem lịch học và thông báo, đổi mật khẩu |
| **Quản trị** | Thêm giáo viên khác (mỗi người có lớp, ngân hàng, đề riêng), xem nhật kí thao tác |

### Gõ công thức hoá học

Gõ bình thường, website tự hạ chỉ số: `H2SO4` → H₂SO₄, `CH3COOC2H5`, `Fe2(SO4)3`, `(C6H10O5)n`.
Điện tích dùng dấu mũ: `Fe^3+`, `SO4^2-`, `NH4^+`. Mũi tên: `->` và `<=>`. Chỉ số tự do: `x_1`, mũ tự do: `10^{-3}`.

### Mẫu dán nhanh câu hỏi

```
Câu 1. [NB] Công thức của ethyl acetate là
A. HCOOC2H5
*B. CH3COOC2H5
C. CH3COOCH3
D. C2H5COOCH3
Lời giải: Ethyl acetate là ester của acetic acid và ethanol.

Câu 2. [TH] Xét các phát biểu về glucose:
a) Glucose là monosaccharide. (Đ)
b) Glucose thuộc loại polymer. (S)
c) Glucose có phản ứng với thuốc thử Tollens. (Đ)
d) Glucose không tan trong nước. (S)

Câu 3. [VD] Cho 18 gam glucose ... Giá trị của m là bao nhiêu?
Đáp án: 21,6
```

Dấu `*` đứng trước phương án đúng; mỗi ý đúng/sai kết thúc bằng `(Đ)` hoặc `(S)`; câu trả lời ngắn có dòng `Đáp án:`.

### Cách tính điểm

- Trắc nghiệm, trả lời ngắn: đúng được trọn điểm câu. Đáp án số chấp nhận dấu phẩy hoặc dấu chấm và sai số do giáo viên đặt.
- Đúng/sai: giáo viên chọn cho từng đề — theo số ý đúng (1 ý 10 %, 2 ý 25 %, 3 ý 50 %, 4 ý 100 % điểm câu) hoặc chia đều 25 % mỗi ý.

## 3. Dữ liệu và sao lưu

Toàn bộ dữ liệu nằm trong thư mục **`data/`** (tệp `tdh.db` và các tệp `tdh.db-wal`, `tdh.db-shm` đi kèm). Sao lưu = dừng website rồi chép cả thư mục `data/` sang nơi khác. Khôi phục = chép ngược lại.

Muốn làm lại từ đầu: dừng website, đổi tên thư mục `data/` (ví dụ `data_cu/`), chạy lại — hệ thống tạo cơ sở dữ liệu mới. Thêm `--no-demo` nếu không cần dữ liệu minh hoạ: `python3 server.py --no-demo`.

## 4. Kiểm thử

```bash
python3 tests/test_api.py
```

Bộ kiểm thử tự khởi động máy chủ riêng trên cơ sở dữ liệu tạm (không đụng tới `data/`), chạy ở cả chế độ máy cá nhân lẫn chế độ máy chủ Internet (WSGI), tổng cộng 133 điểm kiểm tra: đăng nhập, bắt buộc đổi mật khẩu, chặn dò mật khẩu, phân quyền giáo viên/học sinh, học sinh không xem được bài của nhau, giáo viên không xem được lớp của nhau, đề gửi cho học sinh không chứa đáp án, chấm điểm, nộp hai lần, hết giờ tự nộp, số lượt làm, ma trận thiếu câu.

## 5. An toàn dữ liệu — đọc trước khi dùng cho lớp thật

Đã làm ở máy chủ: mật khẩu chỉ lưu dạng băm (PBKDF2-SHA256), phiên đăng nhập bằng cookie HttpOnly, kiểm tra quyền ở mọi API, đáp án và việc chấm điểm chỉ nằm ở máy chủ, giới hạn số lần đăng nhập sai, nhật kí thao tác.

**Chưa có / cần làm trước khi dùng chính thức:**

1. **HTTPS.** Chạy trong Wi-Fi bằng `http` thì mật khẩu đi qua mạng chưa mã hoá. Dùng chính thức cần đưa lên máy chủ có HTTPS.
2. **Đưa lên Internet.** Mã nguồn đã sẵn sàng cho máy chủ Render (HTTPS, đĩa lưu bền, khu vực Singapore) — xem **`TRIEN_KHAI_INTERNET.md`**. Việc tạo tài khoản, thanh toán và bấm triển khai chưa thực hiện.
3. **Quy định của nhà trường** về dữ liệu học sinh. Chỉ nhập họ tên và lớp; không nhập CCCD, địa chỉ, số điện thoại.
4. Chống gian lận mới ở mức đảo câu, đảo phương án, giới hạn thời gian và số lượt; không giám sát camera hay khoá màn hình.

## 6. Chưa làm trong đợt này

Câu tự luận và nộp ảnh bài làm; chấm phiếu trắc nghiệm giấy; đọc trực tiếp tệp Word/PDF/ảnh (hiện dán văn bản); AI soạn câu hỏi; tải tệp lên máy chủ (hiện dùng liên kết Drive/YouTube); gửi email/thông báo đẩy.

## 7. Cấu trúc thư mục

```
server.py            máy chủ: API, phân quyền, chấm điểm, ma trận, sao lưu
wsgi.py              điểm vào khi chạy trên máy chủ Internet (gunicorn)
render.yaml          cấu hình triển khai lên Render; requirements.txt chỉ cần cho máy chủ Internet
TRIEN_KHAI_INTERNET.md  hướng dẫn đưa lên Internet
seed_demo.py         dữ liệu minh hoạ (31 câu Hoá 12, 1 lớp, 1 đề)
static/              giao diện: index.html, app.css, app.js, teacher.js, student.js, img/
tests/test_api.py    kiểm thử tự động
data/                cơ sở dữ liệu (tạo khi chạy lần đầu) — KHÔNG chia sẻ thư mục này
```
