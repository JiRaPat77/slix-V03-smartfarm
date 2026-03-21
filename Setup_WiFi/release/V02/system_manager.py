import time
import threading
import os
import logging
from logging.handlers import RotatingFileHandler
from periphery import GPIO

# --- Logging Configuration ---
LOG_DIR = "/root/Setup_WiFi/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("SystemManager")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(f"{LOG_DIR}/system_manager.log", maxBytes=5*1024*1024, backupCount=2)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Hardware Configuration ---
PIN_WHITE = 54
PIN_RED = 55
PIN_BUTTON = 50

class SystemManager:
    def __init__(self):
        self.white_led = GPIO(PIN_WHITE, "out")
        self.red_led = GPIO(PIN_RED, "out")
        self.button = GPIO(PIN_BUTTON, "in")
        
        self.state = "SETUP"  
        self.running = True
        self.state_lock = threading.Lock()

        logger.info("Initializing System Manager...")

        if os.path.exists("/root/Setup_WiFi/.wifi_setup_done"):
            logger.info("Found WiFi Setup Flag. Resuming normal operation.")
            self.set_state("NORMAL")
            os.system("sh -x /etc/init.d/S99main_service start")
        else:
            logger.info("No WiFi setup flag found. Entering SETUP mode.")
            self.set_state("SETUP")
            os.system("python3 /root/Setup_WiFi/server2.py &")
        
        self.led_thread = threading.Thread(target=self._led_loop)
        self.led_thread.daemon = True
        self.led_thread.start()

        self.net_thread = threading.Thread(target=self._network_watchdog)
        self.net_thread.daemon = True
        self.net_thread.start()

        self.btn_thread = threading.Thread(target=self._button_listener)
        self.btn_thread.daemon = True
        self.btn_thread.start()

    def set_state(self, new_state):
        with self.state_lock:
            if self.state != new_state:
                logger.info(f"State changed from {self.state} to: {new_state}")
                self.state = new_state

    def get_state(self):
        with self.state_lock:
            return self.state

    def _led_loop(self):
        toggle = False
        while self.running:
            current_state = self.get_state()
            
            if current_state == "SETUP":
                self.white_led.write(toggle)
                self.red_led.write(False)
            elif current_state == "NORMAL":
                self.white_led.write(True)
                self.red_led.write(False)
            elif current_state == "ERROR":
                self.white_led.write(False)
                self.red_led.write(toggle)
            elif current_state == "OFF":
                self.white_led.write(False)
                self.red_led.write(False)
            
            toggle = not toggle
            time.sleep(0.5)

    def _check_internet(self):
        response = os.system("ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1")
        return response == 0

    def _network_watchdog(self):
        fail_count = 0
        while self.running:
            is_online = self._check_internet()
            current_state = self.get_state()
            
            if is_online:
                if fail_count > 0:
                    logger.info("Internet connection restored.")
                fail_count = 0
                
                if current_state == "SETUP":
                    self.set_state("NORMAL")
                elif current_state == "ERROR":
                    self.set_state("NORMAL")
            else:
                if current_state in ["NORMAL", "ERROR"]:
                    fail_count += 1
                    logger.debug(f"Internet check failed. Count: {fail_count}/10")
                    
                    if fail_count >= 10 and current_state == "NORMAL":
                        logger.warning("Internet lost 10 consecutive times. Changing to ERROR state.")
                        self.set_state("ERROR")
            
            time.sleep(5)

    def _trigger_factory_reset(self):
        logger.warning("5-Second hold detected. Triggering Factory Reset.")
        self.set_state("OFF")
        time.sleep(5)
        
        logger.info("Clearing WiFi configuration memory...")
        os.system("rm -f /root/Setup_WiFi/.wifi_setup_done")
        os.system("sh -x /etc/init.d/S99main_service stop")
        
        logger.info("Reverting TP-Link to AP Mode...")
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
        
        logger.info("TP-Link is in AP Mode. Ready for setup.")
        self.set_state("SETUP")
        os.system("python3 /root/Setup_WiFi/server2.py &")

    def _button_listener(self):
        press_time = 0
        is_pressing = False
        
        while self.running:
            try:
                btn_state = self.button.read()
                
                if btn_state == False:
                    if not is_pressing:
                        is_pressing = True
                        press_time = 0
                        logger.info("Button pressed. Holding...")
                    else:
                        press_time += 0.2
                        
                    if press_time >= 5.0:
                        self._trigger_factory_reset()
                        
                        while self.button.read() == False:
                            time.sleep(0.5)
                        
                        is_pressing = False
                        press_time = 0
                else:
                    if is_pressing:
                        logger.info("Button released early. Reset cancelled.")
                    is_pressing = False
                    press_time = 0
            
            except Exception as e:
                logger.error(f"Error reading button state: {e}")
                
            time.sleep(0.2)

    def cleanup(self):
        logger.info("Shutting down System Manager...")
        self.running = False
        self.white_led.write(False)
        self.red_led.write(False)
        self.white_led.close()
        self.red_led.close()
        self.button.close()

if __name__ == "__main__":
    sys_man = SystemManager()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Terminated by user.")
    finally:
        sys_man.cleanup()