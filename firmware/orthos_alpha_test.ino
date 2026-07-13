/*
 * Orthos Alpha — Milestone 1 Test Sketch
 * Goal: Confirm XIAO ESP32C3 <-> MPU6050 I2C communication
 * Reads raw accelerometer + gyroscope values, prints to Serial Monitor
 *
 * Wiring:
 *   MPU6050 VCC -> XIAO 3V3
 *   MPU6050 GND -> XIAO GND
 *   MPU6050 SCL -> XIAO D5
 *   MPU6050 SDA -> XIAO D4
 */

#include <Wire.h>

const int MPU_ADDR = 0x68;  // Default I2C address for MPU6050

int16_t accelX, accelY, accelZ;
int16_t gyroX, gyroY, gyroZ;

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10); // wait for serial monitor to open
  }

  Wire.begin();  // uses default SDA/SCL pins on XIAO (D4/D5)

  // Wake up the MPU6050 (it starts in sleep mode by default)
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);  // PWR_MGMT_1 register
  Wire.write(0);     // set to 0 to wake up
  byte error = Wire.endTransmission(true);

  if (error == 0) {
    Serial.println("MPU6050 connected successfully.");
  } else {
    Serial.println("ERROR: Could not connect to MPU6050. Check wiring.");
  }

  delay(500);
}

void loop() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // starting register for accelerometer data
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);  // read 14 registers

  accelX = Wire.read() << 8 | Wire.read();
  accelY = Wire.read() << 8 | Wire.read();
  accelZ = Wire.read() << 8 | Wire.read();

  Wire.read(); Wire.read();  // skip temperature registers (not used yet)

  gyroX = Wire.read() << 8 | Wire.read();
  gyroY = Wire.read() << 8 | Wire.read();
  gyroZ = Wire.read() << 8 | Wire.read();

  Serial.print("AccelX: "); Serial.print(accelX);
  Serial.print(" | AccelY: "); Serial.print(accelY);
  Serial.print(" | AccelZ: "); Serial.print(accelZ);
  Serial.print(" || GyroX: "); Serial.print(gyroX);
  Serial.print(" | GyroY: "); Serial.print(gyroY);
  Serial.print(" | GyroZ: "); Serial.println(gyroZ);

  delay(200);  // ~5 readings per second, easy to read in the monitor
}
