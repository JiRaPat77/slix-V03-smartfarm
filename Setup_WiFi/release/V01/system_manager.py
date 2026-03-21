import time
import threading
import os
from periphery import GPIO

PIN_WHITE = 54
PIN_RED = 55
PIN_BUTTON = 50  # Please change this to your actual button GPIO pin

class SystemManager:
    def __init__(self):
        self.white_led = GPIO(PIN_WHITE, "out")
        self.red_led = GPIO(PIN_RED, "out")
        self.button = GPIO(PIN_BUTTON, "in")
        
        self.state = "SETUP"  
        self.running = True

        if os.path.exists("/root/Setup_WiFi/.wifi_setup_done"):
            print("[System] Found WiFi Setup Flag! Resuming normal operation.")
            self.state = "NORMAL"
            os.system("sh -x /etc/init.d/S99main_service start")
        else:
            print("[System] No WiFi setup found. Entering SETUP mode.")
            self.state = "SETUP"
            os.system("python3 /root/Setup_WiFi/server2.py &")
        
        # Thread 1: LED Controller
        self.led_thread = threading.Thread(target=self._led_loop)
        self.led_thread.daemon = True
        self.led_thread.start()

        # Thread 2: Network Watchdog
        self.net_thread = threading.Thread(target=self._network_watchdog)
        self.net_thread.daemon = True
        self.net_thread.start()

        # Thread 3: Button Listener
        self.btn_thread = threading.Thread(target=self._button_listener)
        self.btn_thread.daemon = True
        self.btn_thread.start()

    def set_state(self, new_state):
        if self.state != new_state:
            print(f"[System] State changed from {self.state} to: {new_state}")
            self.state = new_state

    def _led_loop(self):
        toggle = False
        while self.running:
            if self.state == "SETUP":
                self.white_led.write(toggle)
                self.red_led.write(False)
            elif self.state == "NORMAL":
                self.white_led.write(True)
                self.red_led.write(False)
            elif self.state == "ERROR":
                self.white_led.write(False)
                self.red_led.write(toggle)
            elif self.state == "OFF":
                self.white_led.write(False)
                self.red_led.write(False)
            
            toggle = not toggle
            time.sleep(0.5)

    def _check_internet(self):
        response = os.system("ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1")
        return response == 0

    def _network_watchdog(self):
        while self.running:
            
            is_online = self._check_internet()
            
            if self.state == "SETUP":
           
                if is_online:
                    self.set_state("NORMAL")
            
            elif self.state == "NORMAL":
            
                if not is_online:
                    self.set_state("ERROR")
                    
            elif self.state == "ERROR":

                if is_online:
                    self.set_state("NORMAL")
            
            time.sleep(5)

    def _trigger_factory_reset(self):
        print("\n[!] 5-Second hold detected! Triggering Reset...")
        
        # 1. Turn off all LEDs for 5 seconds to acknowledge user
        self.set_state("OFF")
        time.sleep(5)

        print("[System] Clearing WiFi configuration memory...")
        os.system("rm -f /root/Setup_WiFi/.wifi_setup_done")
        os.system("sh /etc/init.d/S99main_service stop")
        
        # 2. Revert TP-Link to AP Mode
        print("[System] Reverting TP-Link to AP Mode...")
        uci_commands = (
            "uci set wireless.radio0.disabled='0'; "
            "uci set wireless.@wifi-iface[0].mode='ap'; "
            "uci set wireless.@wifi-iface[0].network='lan'; "
            "uci set wireless.@wifi-iface[0].ssid='SmartFarm_Setup'; "
            "uci set wireless.@wifi-iface[0].encryption='none'; "
            "uci commit wireless; "
            "wifi reload; "
            "/etc/init.d/network restart"
        )
        cmd = f'ssh -i /root/.ssh/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/root/.ssh/known_hosts_tplink root@192.168.1.1 "{uci_commands}"'
        os.system(cmd)
        
        # 3. Change state back to SETUP
        print("[System] TP-Link is in AP Mode. Ready for setup.")
        self.set_state("SETUP")
        os.system("python3 /root/Setup_WiFi/server2.py &")

    def _button_listener(self):
        press_time = 0
        is_pressing = False
        
        while self.running:
            try:
                # Active Low: False means pressed (connected to GND)
                btn_state = self.button.read()
                
                if btn_state == False:
                    if not is_pressing:
                        is_pressing = True
                        press_time = 0
                        print("[Button] Pressed. Holding...")
                    else:
                        press_time += 0.2
                        
                    if press_time >= 5.0:
                        self._trigger_factory_reset()
                        
                        # Wait until user releases the button
                        while self.button.read() == False:
                            time.sleep(0.5)
                        
                        is_pressing = False
                        press_time = 0
                else:
                    if is_pressing:
                        print("[Button] Released early. Reset cancelled.")
                    is_pressing = False
                    press_time = 0
            except Exception as e:
                pass
                
            time.sleep(0.2)

    def cleanup(self):
        self.running = False
        self.white_led.write(False)
        self.red_led.write(False)
        self.white_led.close()
        self.red_led.close()
        self.button.close()

if __name__ == "__main__":
    print("=== Starting System Manager (Button Listener) ===")
    sys_man = SystemManager()
    
    try:
        print("[Test] System is in NORMAL mode.")
        sys_man.set_state("NORMAL")
        
        print("\n*** ACTION REQUIRED ***")
        print(f"Please press and hold the button on GPIO {PIN_BUTTON} for 5 seconds.")
        print("The LEDs should turn OFF for 5 seconds, then return to SETUP mode (White blinking).")
        print("Press Ctrl+C to exit this test.\n")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTest terminated by user")
    finally:
        sys_man.cleanup()
        print("GPIO ports closed")