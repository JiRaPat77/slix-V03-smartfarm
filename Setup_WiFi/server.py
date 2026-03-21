from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import os
import time

ROUTER_IP = "192.168.1.1"
ROUTER_USER = "root"


html_page = """
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; }
        .container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); display: inline-block; width: 80%; max-width: 300px; }
        input { margin: 10px 0; padding: 10px; width: 90%; border: 1px solid #ccc; border-radius: 5px; }
        button { padding: 10px 20px; width: 100%; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>ตั้งค่า WiFi<br>Smart Farm</h2>
        <form method="POST" action="/setup">
            <input type="text" name="ssid" placeholder="ชื่อ WiFi (SSID)" required><br>
            <input type="password" name="password" placeholder="รหัสผ่าน WiFi" required><br>
            <button type="submit">เชื่อมต่อ</button>
        </form>
    </div>
</body>
</html>
"""

def setup_openwrt_cmd(ssid, password):
    print(f"\n[*] Starting configuration via System SSH for SSID: {ssid}")
    
    uci_commands = (
        f"uci set wireless.radio0.disabled='0'; "
        f"uci set wireless.radio0.channel='auto'; "
        f"uci set wireless.@wifi-iface[0].device='radio0'; "
        f"uci set wireless.@wifi-iface[0].mode='sta'; "
        f"uci set wireless.@wifi-iface[0].network='wwan'; "
        f"uci set wireless.@wifi-iface[0].ssid='{ssid}'; "
        f"uci set wireless.@wifi-iface[0].encryption='psk2'; "
        f"uci set wireless.@wifi-iface[0].key='{password}'; "
        f"uci set network.wwan=interface; "
        f"uci set network.wwan.proto='dhcp'; "
        f"uci set firewall.@zone[1].network='wan wan6 wwan'; "
        f"uci commit wireless; "
        f"uci commit network; "
        f"uci commit firewall; "
        f"wifi reload; "
        f"/etc/init.d/network restart; "
        f"/etc/init.d/firewall restart;"
    )

    
    full_cmd = f'ssh -i /root/.ssh/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/root/.ssh/known_hosts_tplink {ROUTER_USER}@{ROUTER_IP} "{uci_commands}"'
    
    print(f"[#] Executing System Call...")
    exit_code = os.system(full_cmd)
    
    if exit_code == 0:
        print("[+] Success: Commands executed on OpenWRT")
        return True
    else:
        print(f"[-] Error: System call failed with exit code {exit_code}")
        return False

class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_page.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = urllib.parse.parse_qs(post_data)
        
        ssid = parsed_data.get('ssid', [''])[0]
        password = parsed_data.get('password', [''])[0]
        
        success = setup_openwrt_cmd(ssid, password)
        
        if success:
            response = "<h3>ตั้งค่าสำเร็จ!</h3><p>ระบบกำลังเชื่อมต่อกับ WiFi ของฟาร์ม... กรุณารอสักครู่</p>"
        else:
            response = "<h3>เกิดข้อผิดพลาด</h3><p>ไม่สามารถเชื่อมต่อกับ TP-Link ได้ (SSH Error)</p>"

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

print("Starting Smart Farm Setup Server at http://192.168.1.100 ...")
server = HTTPServer(('0.0.0.0', 80), WebServerHandler)
server.serve_forever()