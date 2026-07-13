/*
 * Orthos Alpha — Milestone 2: Calibration
 * 
 * Step 1: Convert raw values to real-world units (g-force, deg/s)
 * Step 2: Compute bias offsets while sensor is still and flat
 *
 * INSTRUCTIONS:
 * 1. Place the MPU6050 on a flat, level, motionless surface (e.g. desk)
 * 2. Upload this sketch and open Serial Monitor at 115200 baud
 * 3. Do NOT touch the breadboard during calibration (~3 seconds)
 * 4. Copy the printed offset values — you'll need them in the next sketch
 */

#include <Wire.h>

const int MPU_ADDR = 0x68;

int16_t rawAccelX, rawAccelY, rawAccelZ;
int16_t rawGyroX, rawGyroY, rawGyroZ;

// MPU6050 default sensitivity scale factors (datasheet values)
// Accelerometer: +/- 2g range -> 16384 LSB/g
// Gyroscope: +/- 250 deg/s range -> 131 LSB/(deg/s)
const float ACCEL_SCALE = 16384.0;
const float GYRO_SCALE = 131.0;

// Calibration variables
float accelXOffset = 0, accelYOffset = 0, accelZOffset = 0;
float gyroXOffset = 0, gyroYOffset = 0, gyroZOffset = 0;

const int CALIBRATION_SAMPLES = 2000;

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Wire.begin();

  // Wake up MPU6050
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  delay(500);

  Serial.println("=== ORTHOS CALIBRATION ===");
  Serial.println("Warming up sensor for 20 seconds. Keep it FLAT and STILL...");
  delay(20000); // let the chip's internal temperature stabilize before calibrating

  Serial.println("Warm-up complete. Calibrating now — do NOT touch anything...");
  calibrateSensor();

  Serial.println("=== CALIBRATION COMPLETE ===");
  Serial.println("Copy these offset values for the next sketch:");
  Serial.print("accelXOffset = "); Serial.println(accelXOffset, 4);
  Serial.print("accelYOffset = "); Serial.println(accelYOffset, 4);
  Serial.print("accelZOffset = "); Serial.println(accelZOffset, 4);
  Serial.print("gyroXOffset = "); Serial.println(gyroXOffset, 4);
  Serial.print("gyroYOffset = "); Serial.println(gyroYOffset, 4);
  Serial.print("gyroZOffset = "); Serial.println(gyroZOffset, 4);
  Serial.println("===========================");
  Serial.println("Now printing live calibrated values:");
  delay(1000);
}

void readRawData() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);

  rawAccelX = Wire.read() << 8 | Wire.read();
  rawAccelY = Wire.read() << 8 | Wire.read();
  rawAccelZ = Wire.read() << 8 | Wire.read();

  Wire.read(); Wire.read(); // skip temperature

  rawGyroX = Wire.read() << 8 | Wire.read();
  rawGyroY = Wire.read() << 8 | Wire.read();
  rawGyroZ = Wire.read() << 8 | Wire.read();
}

void calibrateSensor() {
  float sumAccelX = 0, sumAccelY = 0, sumAccelZ = 0;
  float sumGyroX = 0, sumGyroY = 0, sumGyroZ = 0;

  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    readRawData();

    sumAccelX += rawAccelX / ACCEL_SCALE;
    sumAccelY += rawAccelY / ACCEL_SCALE;
    sumAccelZ += rawAccelZ / ACCEL_SCALE;

    sumGyroX += rawGyroX / GYRO_SCALE;
    sumGyroY += rawGyroY / GYRO_SCALE;
    sumGyroZ += rawGyroZ / GYRO_SCALE;

    delay(4); // ~250 samples/sec pacing, settles ~2 sec total
  }

  // Average accelerometer readings = the offset/bias
  // Note: Z-axis offset subtracts 1g separately later, since gravity is expected on Z
  accelXOffset = sumAccelX / CALIBRATION_SAMPLES;
  accelYOffset = sumAccelY / CALIBRATION_SAMPLES;
  accelZOffset = (sumAccelZ / CALIBRATION_SAMPLES) - 1.0; // subtract expected 1g

  // Average gyro readings = the offset/bias (should be ~0 when still)
  gyroXOffset = sumGyroX / CALIBRATION_SAMPLES;
  gyroYOffset = sumGyroY / CALIBRATION_SAMPLES;
  gyroZOffset = sumGyroZ / CALIBRATION_SAMPLES;
}

void loop() {
  readRawData();

  float accelX_g = (rawAccelX / ACCEL_SCALE) - accelXOffset;
  float accelY_g = (rawAccelY / ACCEL_SCALE) - accelYOffset;
  float accelZ_g = (rawAccelZ / ACCEL_SCALE) - accelZOffset;

  float gyroX_dps = (rawGyroX / GYRO_SCALE) - gyroXOffset;
  float gyroY_dps = (rawGyroY / GYRO_SCALE) - gyroYOffset;
  float gyroZ_dps = (rawGyroZ / GYRO_SCALE) - gyroZOffset;

  Serial.print("AccelX(g): "); Serial.print(accelX_g, 3);
  Serial.print(" | AccelY(g): "); Serial.print(accelY_g, 3);
  Serial.print(" | AccelZ(g): "); Serial.print(accelZ_g, 3);
  Serial.print(" || GyroX(dps): "); Serial.print(gyroX_dps, 2);
  Serial.print(" | GyroY(dps): "); Serial.print(gyroY_dps, 2);
  Serial.print(" | GyroZ(dps): "); Serial.println(gyroZ_dps, 2);

  delay(100); // ~10 readings per second for easy reading
}
