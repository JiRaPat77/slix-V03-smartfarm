import serial
import time
import struct

class SensorAirTempHumidityRS30:

    def __init__(self, port="/dev/ttyS2", slave_address=1, baudrate=9600, timeout=1.0):
        self.port = port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.timeout = timeout
        
        # Mapping ค่า Baudrate ตามคู่มือ 
        self.BAUD_MAP = {
            2400: 0, 4800: 1, 9600: 2, 
            19200: 3, 38400: 4, 57600: 5, 115200: 6
        }
        # สร้าง Map กลับสำหรับอ่านค่า
        self.BAUD_MAP_REVERSE = {v: k for k, v in self.BAUD_MAP.items()}

    @staticmethod
    def modbus_crc(data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 1) != 0:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def _send_command(self, address, function_code, start_reg, data_val):
        try:
            ser = serial.Serial(
                port=self.port, 
                baudrate=self.baudrate, 
                bytesize=8, 
                parity='N', 
                stopbits=1, 
                timeout=self.timeout
            )
            
           
            cmd = [address, function_code, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (data_val >> 8) & 0xFF, data_val & 0xFF]
            crc = self.modbus_crc(cmd)
            cmd.append(crc & 0xFF)
            cmd.append((crc >> 8) & 0xFF)
            ser.reset_input_buffer()
            ser.write(bytearray(cmd))
            response = ser.read(128)
            ser.close()
            
            if len(response) < 5:
                return None, "No response or incomplete"
            resp_list = list(response)
            
            msg_crc = (resp_list[-1] << 8) | resp_list[-2]
            calc_crc = self.modbus_crc(resp_list[:-2])
            
            if msg_crc != calc_crc:
                return None, f"CRC Error (Exp: {hex(calc_crc)}, Got: {hex(msg_crc)})"
                
            return resp_list, None
            
        except Exception as e:
            return None, f"Serial Error: {e}"

    def read_temp(self):
        resp, err = self._send_command(self.slave_address, 0x03, 0x0000, 0x0002)
        
        if err or not resp:
            print(f"Read Error: {err}")
            return None
            
        try:
            # Response: [Addr, 03, Bytes, HumH, HumL, TempH, TempL, CRCL, CRCH]
            if len(resp) < 9: return None
            
            # Humidity (0x0000)
            hum_raw = (resp[3] << 8) | resp[4]
            humidity = hum_raw / 10.0
            
            # Temperature (0x0001) - Signed Value! [cite: 198]
            temp_raw = (resp[5] << 8) | resp[6]
            if temp_raw >= 0x8000:
                temp_raw -= 0x10000 # แปลง Two's complement
            temperature = temp_raw / 10.0
            
            if (temperature < -40 or temperature > 120) or (humidity < 0 or humidity > 100):
                raise ValueError(f"Sensor incorrect value (Temperature: {temperature}, Moisture: {humidity})")
            
            return {
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1)
            }
        except Exception as e:
            print(f"Parse Error: {e}")
            return None

    #Check address
    def check_address(self):
        resp, err = self._send_command(0xFF, 0x03, 0x07D0, 0x0001)
        
        if err:
            print(f"Check Address Failed: {err}")
            return None
            
        found_address = (resp[3] << 8) | resp[4]
        return found_address

    # Change Address
    def set_address(self, new_address):

        if not (1 <= new_address <= 247):
            print("Error: Address must be 1-247")
            return False
            
        print(f"Changing Address from {self.slave_address} to {new_address}...")
        resp, err = self._send_command(self.slave_address, 0x06, 0x07D0, new_address)
        
        if err:
            print(f"Set Address Failed: {err}")
            return False
            
        if resp[4] == (new_address >> 8) & 0xFF and resp[5] == new_address & 0xFF:
            self.slave_address = new_address
            print(f"Address changed to {new_address}")
            return True
        return False

    # Reset to Factory
    def reset_to_default(self):
        print("Resetting to Factory Defaults...")
        
        # 1. Reset Address -> 1
        success_addr = self.set_address(1)
        
        # 2. Reset Baudrate -> 4800 (Value = 1)
        original_addr = self.slave_address
        self.slave_address = 1 
        
        # Register 0x07D1, Value 1 = 4800bps 
        resp, err = self._send_command(self.slave_address, 0x06, 0x07D1, 1)
        
        if err:
            print(f"Reset Baudrate Failed: {err}")
            self.slave_address = original_addr 
            return False
            
        if resp[5] == 1:
            self.baudrate = 4800
            print("Baudrate reset to 4800")
            print("Factory Reset Complete (Addr: 1, Baud: 4800)")
            return True
            
        return False

    def calibrate(self, temp_offset=0.0, hum_offset=0.0):
        """
        ตั้งค่า Calibration (Offset)
        Reg 0x0050: Temp Offset
        Reg 0x0051: Hum Offset
        
        """
        # Convert to int16 format (x10)
        t_val = int(temp_offset * 10)
        h_val = int(hum_offset * 10)
        
        # Handle Negative Values (Two's complement)
        if t_val < 0: t_val += 0x10000
        if h_val < 0: h_val += 0x10000
        
        # Send Temp Calibration
        self._send_command(self.slave_address, 0x06, 0x0050, t_val)
        # Send Hum Calibration
        self._send_command(self.slave_address, 0x06, 0x0051, h_val)
        print(f"Calibrated: Temp {temp_offset}, Hum {hum_offset}")