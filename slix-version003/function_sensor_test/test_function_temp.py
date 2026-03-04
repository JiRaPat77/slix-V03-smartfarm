#!/usr/bin/env python3
import time
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from class_sensor.class_temp_modbus import SensorAirTempHumidityRS30


PORT = "/dev/ttyS1" 
ADDR = 2        # Address ของ Sensor
BAUD = 9600     # Baudrate ของ Sensor


def main():
    print(f"--- Start Testing Sensor on {PORT} (Addr: {ADDR}) ---")
    
  
    sensor = SensorAirTempHumidityRS30(port=PORT, slave_address=ADDR, baudrate=BAUD)
    try:
        print("Reading data...")
        data = sensor.read_temp()
        if data:
            print(f"Read Success: Temp={data['temperature']}°C, Hum={data['humidity']}%")
        else:
            print("Read Failed (No response)")
    except Exception as e:
        print(f"Error: {e}")

    # Check Address
    # real_addr = sensor.check_address()
    # if real_addr:
    #     print(f"Found Sensor Address: {real_addr}")

    # Chance Address
    # NEW_ADDR = 2
    # if sensor.set_address(NEW_ADDR):
    #     print(f"Address changed to {NEW_ADDR}")

    # Reset to default address
    # sensor.reset_to_default()

if __name__ == "__main__":
    main()