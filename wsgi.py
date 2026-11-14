# -*- coding: utf-8 -*-
"""Điểm vào WSGI của TĐH Chemistry — dùng trên máy chủ Internet.

    gunicorn wsgi:application --preload --workers 2 --threads 8 --bind 0.0.0.0:$PORT

Cấu hình qua biến môi trường: TDH_DATA (thư mục dữ liệu), TDH_SECURE_COOKIE=1, TDH_TRUST_PROXY=1,
TDH_NO_DEMO=1, TDH_ADMIN_PASSWORD (mật khẩu ban đầu của tài khoản giaovien), TZ=Asia/Ho_Chi_Minh.
"""
import server

server.configure()
application = server.wsgi_app

if __name__ == '__main__':                  # chạy thử bằng máy chủ WSGI có sẵn của Python
    import sys
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8700
    print('TĐH Chemistry (WSGI) đang chạy:  http://localhost:%d' % port)
    make_server('127.0.0.1', port, application, handler_class=Quiet).serve_forever()
