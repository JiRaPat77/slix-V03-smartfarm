#!/usr/bin/env python3
import sys
import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from class_sensor.class_ultra_modbus import UltrasonicModbus


sensor = UltrasonicModbus(port="/dev/ttyS2", slave_address=0x4C, baudrate=9600)
data = sensor.read_distance()
print(json.dumps(data, indent=2, ensure_ascii=False))
