/*
 * Orthos Alpha — I2C Scanner / Debug Tool
 * Scans the I2C bus and reports any devices found with their address.
 * Use this to confirm the MPU6050 is actually being detected on the bus.
 */

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }
  delay(1000);
  Wire.begin();
  Serial.println("\nI2C Scanner starting...");
}

void loop() {
  byte error, address;
  int devicesFound = 0;

  Serial.println("Scanning...");

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("Device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      devicesFound++;
    }
  }

  if (devicesFound == 0) {
    Serial.println("No I2C devices found. Check wiring.");
  } else {
    Serial.print(devicesFound);
    Serial.println(" device(s) found.");
  }

  delay(3000);
}
