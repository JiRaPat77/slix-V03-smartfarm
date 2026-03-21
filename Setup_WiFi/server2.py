import http.server
import socketserver
import urllib.parse
import os
import time
import threading

PORT = 80

class SetupHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Smart Farm Setup</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: sans-serif; text-align: center; margin-top: 50px; }
                    input[type="text"], input[type="password"] { padding: 10px; width: 80%; max-width: 300px; margin-bottom: 20px; }
                    input[type="submit"] { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                </style>
            </head>
            <body>
                <h2>ตั้งค่า WiFi สำหรับ Smart Farm</h2>
                <form method="POST" action="/setup">
                    ชื่อ WiFi (SSID): <br>
                    <input type="text" name="ssid" required><br>
                    รหัสผ่าน (Password): <br>
                    <input type="password" name="password"><br>
                    <input type="submit" value="เชื่อมต่อ">
                </form>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/setup':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data)
            
            ssid = parsed_data.get('ssid', [''])[0]
            password = parsed_data.get('password', [''])[0]

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Setup Complete</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #f0f8ff; }
                    h2 { color: #2e8b57; }
                </style>
            </head>
            <body>
                <h2>การตั้งค่า WIFI เสร็จสิ้น</h2>
                <p>กรุณารอสักครู่ ระบบกำลังทำการเชื่อมต่อ</p>
                <p>หากการเชื่อมต่อสำเร็จ สัญญาณไฟสีขาวจะติดค้าง</p>
                <p style="color: gray; font-size: 0.9em;">(คุณสามารถปิดหน้านี้ได้เลย)</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode('utf-8'))

            threading.Thread(target=self.apply_network_settings, args=(ssid, password)).start()

    def apply_network_settings(self, ssid, password):
        print(f"\n[Server] Received target WiFi SSID: {ssid}")
        
        time.sleep(2)
        
        print("[Server] Sending configuration to TP-Link...")
        uci_commands = (
            f"uci set wireless.@wifi-iface[0].mode='sta'; "
            f"uci set wireless.@wifi-iface[0].network='wwan'; "
            f"uci set wireless.@wifi-iface[0].ssid='{ssid}'; "
            f"uci set wireless.@wifi-iface[0].key='{password}'; "
            f"uci set wireless.@wifi-iface[0].encryption='psk2'; "
            f"uci commit wireless; "
            f"wifi reload; "
            f"/etc/init.d/network restart"
        )
        
        cmd = f'ssh -i /root/.ssh/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/root/.ssh/known_hosts_tplink root@192.168.1.1 "{uci_commands}"'
        os.system(cmd)

        print("[Server] Creating WiFi Setup Flag File...")
        os.system("touch /root/Setup_WiFi/.wifi_setup_done")
        
        print("[Server] Starting main_controller.py...")
        os.system("sh -x /etc/init.d/S99main_service start")
        
        print("[Server] Setup finished. Shutting down web server...")
        os._exit(0)

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), SetupHandler) as httpd:
        print(f"=== Web Setup Server is running on port {PORT} ===")
        httpd.serve_forever()