/*
 * Complete Spectral + UV Data Logger
 * For Adalogger RP2040 with DS3231 RTC and SD card
 * 
 * AS7341: 10 channels (415-910nm) - Visible + NIR
 * TSL2591: Visible + IR Lux
 * AS7263: 6 channels (610-860nm) - Detailed NIR
 * LTR390: UV Index + UVA + Ambient Light
 */

#include <Wire.h>
#include <SPI.h>
#include "SdFat.h"
#include <RTClib.h>
#include <Adafruit_AS7341.h>
#include <Adafruit_TSL2591.h>
#include <AS726X.h>  // SparkFun AS726X library for AS7263
#include <Adafruit_LTR390.h>  // Adafruit LTR390 UV sensor

// =====================
// Hardware / objects
// =====================
Adafruit_AS7341 as7341;   // I2C AS7341 (spectral sensor) - 0x39
Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591);  // I2C TSL2591 (lux sensor) - 0x29
AS726X as7263;            // I2C AS7263 (NIR sensor) - 0x49
Adafruit_LTR390 ltr390;   // I2C LTR390 (UV sensor) - 0x53
RTC_DS3231 rtc;           // DS3231 RTC - 0x68

// --- SD on Adalogger RP2040 (SPI1 + CS=23) ---
#define SD_CS_PIN 23
SdFat SD;
FsFile dataFile;
SdSpiConfig sdConfig(SD_CS_PIN, DEDICATED_SPI, SD_SCK_MHZ(16), &SPI1);

// =====================
// Logging settings
// =====================
const unsigned long LOG_INTERVAL_MS = 10000;   // 10 seconds
unsigned long lastLog = 0;

char filename[32];

// Heartbeat LED - flash once every 5 seconds
const unsigned long HEARTBEAT_INTERVAL = 5000;  // 5 seconds between flashes
const unsigned long HEARTBEAT_FLASH_DURATION = 100;  // LED on for 100ms
unsigned long lastHeartbeat = 0;
bool heartbeatActive = false;
unsigned long heartbeatStartTime = 0;

// =====================
// Helper functions
// =====================
void makeIncrementingFilename() {
  // Start with base name
  if (!SD.exists("SPECLOG.CSV")) {
    strcpy(filename, "SPECLOG.CSV");
    return;
  }
  
  // Try A-Z suffixes
  for (char c = 'A'; c <= 'Z'; c++) {
    snprintf(filename, sizeof(filename), "SPECLOG%c.CSV", c);
    if (!SD.exists(filename)) return;
  }
  
  // Try 0-9 if A-Z are used
  for (char n = '0'; n <= '9'; n++) {
    snprintf(filename, sizeof(filename), "SPECLOG%c.CSV", n);
    if (!SD.exists(filename)) return;
  }
  
  // Fallback
  strcpy(filename, "SPECLOGZ.CSV");
}

void writeHeaderIfNewFile() {
  // If file doesn't exist, create and write header
  bool exists = SD.exists(filename);
  dataFile = SD.open(filename, FILE_WRITE);
  if (!dataFile) {
    Serial.println("ERROR: Could not open log file for writing!");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(100);
      digitalWrite(LED_BUILTIN, LOW);
      delay(100);
    }
  }

  if (!exists) {
    // Write metadata comment
    DateTime now = rtc.now();
    dataFile.print("# Complete Spectral + UV Logger Started: ");
    dataFile.print(now.year()); dataFile.print('-');
    if (now.month() < 10) dataFile.print('0');
    dataFile.print(now.month()); dataFile.print('-');
    if (now.day() < 10) dataFile.print('0');
    dataFile.print(now.day()); dataFile.print(' ');
    if (now.hour() < 10) dataFile.print('0');
    dataFile.print(now.hour()); dataFile.print(':');
    if (now.minute() < 10) dataFile.print('0');
    dataFile.print(now.minute()); dataFile.print(':');
    if (now.second() < 10) dataFile.print('0');
    dataFile.println(now.second());
    dataFile.print("# Log File: ");
    dataFile.println(filename);
    dataFile.println("# Sensors: AS7341 (VIS+NIR) + TSL2591 (Lux) + AS7263 (NIR) + LTR390 (UV)");
    dataFile.println("#");
    
    // Write header
    // AS7341: F1-F8, NIR, Clear
    // TSL2591: Lux_Visible, Lux_IR
    // AS7263: R_610nm, S_680nm, T_730nm, U_760nm, V_810nm, W_860nm
    // LTR390: UV_Index, UVA, ALS (Ambient Light)
    dataFile.println("Date,Time,Time_s,F1_415nm,F2_445nm,F3_480nm,F4_515nm,F5_555nm,F6_590nm,F7_630nm,F8_680nm,NIR_910nm,Clear,Lux_Visible,Lux_IR,R_610nm,S_680nm,T_730nm,U_760nm,V_810nm,W_860nm,UV_Index,UVA,ALS");
    dataFile.flush();
  }
  dataFile.close();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 3000) delay(10);
  delay(100);

  Serial.println("\nComplete Spectral + UV Logger (Adalogger RP2040)");
  Serial.println("==================================================");

  // Blink to show we're alive
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }

  Wire.begin();

  // ----- RTC -----
  Serial.print("Initializing RTC... ");
  if (!rtc.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: DS3231 RTC not found on I2C!");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(500);
      digitalWrite(LED_BUILTIN, LOW);
      delay(500);
    }
  }
  if (rtc.lostPower()) {
    Serial.println("RTC lost power, setting to compile time...");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
  Serial.println("OK.");

  // ----- AS7341 -----
  Serial.print("Initializing AS7341... ");
  if (!as7341.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: AS7341 not found on I2C!");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(200);
      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }
  }
  Serial.println("OK.");

  // Configure AS7341 settings for sunny day
  as7341.setATIME(100);
  as7341.setASTEP(999);
  as7341.setGain(AS7341_GAIN_0_5X);  // 0.5x gain for sunny
  
  Serial.println("AS7341 configured:");
  Serial.println("  ATIME: 100");
  Serial.println("  ASTEP: 999");
  Serial.println("  Gain: 0.5X (sunny)");

  // ----- TSL2591 -----
  Serial.print("Initializing TSL2591... ");
  if (!tsl.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: TSL2591 not found on I2C!");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(300);
      digitalWrite(LED_BUILTIN, LOW);
      delay(300);
    }
  }
  Serial.println("OK.");
  
  // Configure TSL2591 settings for sunny day
  tsl.setGain(TSL2591_GAIN_LOW);
  tsl.setTiming(TSL2591_INTEGRATIONTIME_100MS);
  
  Serial.println("TSL2591 configured:");
  Serial.println("  Gain: LOW (1x) - sunny");
  Serial.println("  Integration: 100ms");

  // ----- AS7263 -----
  Serial.print("Initializing AS7263... ");
  if (!as7263.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: AS7263 not found on I2C!");
    Serial.println("Check wiring and I2C address (should be 0x49).");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(400);
      digitalWrite(LED_BUILTIN, LOW);
      delay(400);
    }
  }
  Serial.println("OK.");
  
  // Configure AS7263 settings for sunny day
  as7263.setGain(2);               // Gain: 0=1x, 1=3.7x, 2=16x, 3=64x
  as7263.setIntegrationTime(50);   // 50 * 2.8ms = 140ms integration
  as7263.setMeasurementMode(2);    // Mode: 2=one-shot
  as7263.disableIndicator();       // Turn off LED indicator
  
  Serial.println("AS7263 configured:");
  Serial.println("  Gain: 16X (sunny)");
  Serial.println("  Integration: 140ms");
  Serial.println("  Mode: One-shot");

  // ----- LTR390 UV Sensor -----
  Serial.print("Initializing LTR390... ");
  if (!ltr390.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: LTR390 not found on I2C!");
    Serial.println("Check wiring and I2C address (should be 0x53).");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(250);
      digitalWrite(LED_BUILTIN, LOW);
      delay(250);
    }
  }
  Serial.println("OK.");
  
  // Configure LTR390 settings
  ltr390.setMode(LTR390_MODE_UVS);  // UV sensing mode
  ltr390.setGain(LTR390_GAIN_3);    // Gain 3 (medium sensitivity)
  ltr390.setResolution(LTR390_RESOLUTION_18BIT);  // 18-bit resolution
  
  Serial.println("LTR390 configured:");
  Serial.println("  Mode: UV sensing");
  Serial.println("  Gain: 3X");
  Serial.println("  Resolution: 18-bit");

  // ----- SD -----
  Serial.print("Initializing SD... ");
  while (!SD.begin(sdConfig)) {
    Serial.println("failed. Retrying...");
    delay(1000);
  }
  Serial.println("OK.");

  makeIncrementingFilename();
  writeHeaderIfNewFile();

  Serial.print("Logging to: ");
  Serial.println(filename);
  Serial.println("==================================================");
  
  // Success - blink 5 times
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
}

void loop() {
  unsigned long currentTime = millis();
  
  // Heartbeat LED - single flash every 5 seconds
  if (!heartbeatActive && (currentTime - lastHeartbeat >= HEARTBEAT_INTERVAL)) {
    // Start a flash
    digitalWrite(LED_BUILTIN, HIGH);
    heartbeatActive = true;
    heartbeatStartTime = currentTime;
    lastHeartbeat = currentTime;
  }
  
  if (heartbeatActive && (currentTime - heartbeatStartTime >= HEARTBEAT_FLASH_DURATION)) {
    // End the flash
    digitalWrite(LED_BUILTIN, LOW);
    heartbeatActive = false;
  }
  
  // Check if it's time to log
  if (currentTime - lastLog < LOG_INTERVAL_MS) return;
  lastLog = currentTime;

  Serial.println("Starting sensor readings...");

  // Read AS7341 spectral data
  uint16_t as7341_readings[12];
  Serial.print("Reading AS7341... ");
  if (!as7341.readAllChannels(as7341_readings)) {
    Serial.println("FAILED!");
    Serial.println("WARNING: AS7341 reading failed, skipping.");
    return;
  }
  Serial.println("OK");

  // Read TSL2591 lux values
  Serial.print("Reading TSL2591... ");
  uint32_t lum = tsl.getFullLuminosity();
  uint16_t ir = lum >> 16;
  uint16_t full = lum & 0xFFFF;
  
  float lux_visible = tsl.calculateLux(full, ir);
  Serial.println("OK");
  
  // Calculate IR lux estimate
  float lux_ir = 0.0;
  if (ir > 0) {
    uint16_t gain_val = 1;  // LOW gain
    uint16_t time_val = 100; // 100ms
    lux_ir = ((float)ir / ((float)gain_val * (float)time_val / 100.0)) * 0.46;
  }

  // Read AS7263 NIR data
  // NOTE: Direct read method (dataAvailable() flag doesn't work on this sensor)
  Serial.print("Reading AS7263... ");
  delay(200);  // Wait for integration time (140ms + margin)
  
  // Get calibrated values directly
  float nir_r = as7263.getCalibratedR();  // 610nm
  float nir_s = as7263.getCalibratedS();  // 680nm
  float nir_t = as7263.getCalibratedT();  // 730nm
  float nir_u = as7263.getCalibratedU();  // 760nm
  float nir_v = as7263.getCalibratedV();  // 810nm
  float nir_w = as7263.getCalibratedW();  // 860nm
  Serial.println("OK");

  // Read LTR390 UV data
  Serial.print("Reading LTR390... ");
  
  // Read UVS (UV sensor mode)
  if (ltr390.newDataAvailable()) {
    uint32_t uv_raw = ltr390.readUVS();
    
    // Calculate UV Index - calibrated for Denver sunny conditions
    // Empirically determined: ~100 counts per UV Index unit at Gain 3X
    float uv_index = (float)uv_raw / 100.0;  // ← MUCH BETTER!
    
    // Get UVA reading (same as UV raw for this sensor)
    float uva = (float)uv_raw;
    
    // Switch to ALS mode to get ambient light
    ltr390.setMode(LTR390_MODE_ALS);
    delay(100);  // Wait for mode switch
    
    float als = 0.0;
    if (ltr390.newDataAvailable()) {
      als = (float)ltr390.readALS();
    }
    
    // Switch back to UV mode for next reading
    ltr390.setMode(LTR390_MODE_UVS);
    
    Serial.println("OK");
    
    // Timestamp
    DateTime now = rtc.now();
    char dateStr[11];
    char timeStr[9];
    snprintf(dateStr, sizeof(dateStr), "%04d-%02d-%02d", now.year(), now.month(), now.day());
    snprintf(timeStr, sizeof(timeStr), "%02d:%02d:%02d", now.hour(), now.minute(), now.second());

    Serial.println("All sensors read successfully!");

    // Open file and write data
    dataFile = SD.open(filename, FILE_WRITE);
    if (!dataFile) {
      Serial.println("ERROR: Could not open log file!");
      return;
    }

    // Write: Date, Time, Time_s, AS7341 (F1-F8, NIR, Clear), TSL2591 (Lux_Vis, Lux_IR), 
    //        AS7263 (R-W), LTR390 (UV_Index, UVA, ALS)
    dataFile.print(dateStr);
    dataFile.print(",");
    dataFile.print(timeStr);
    dataFile.print(",");
    dataFile.print(now.unixtime());
    dataFile.print(",");
    
    // AS7341 channels
    dataFile.print(as7341_readings[0]);   // F1 - 415nm
    dataFile.print(",");
    dataFile.print(as7341_readings[1]);   // F2 - 445nm
    dataFile.print(",");
    dataFile.print(as7341_readings[2]);   // F3 - 480nm
    dataFile.print(",");
    dataFile.print(as7341_readings[3]);   // F4 - 515nm
    dataFile.print(",");
    dataFile.print(as7341_readings[4]);   // F5 - 555nm
    dataFile.print(",");
    dataFile.print(as7341_readings[5]);   // F6 - 590nm
    dataFile.print(",");
    dataFile.print(as7341_readings[6]);   // F7 - 630nm
    dataFile.print(",");
    dataFile.print(as7341_readings[7]);   // F8 - 680nm
    dataFile.print(",");
    dataFile.print(as7341_readings[9]);   // NIR - 910nm
    dataFile.print(",");
    dataFile.print(as7341_readings[10]);  // Clear
    dataFile.print(",");
    
    // TSL2591 lux
    dataFile.print(lux_visible, 2);
    dataFile.print(",");
    dataFile.print(lux_ir, 2);
    dataFile.print(",");
    
    // AS7263 NIR channels
    dataFile.print(nir_r, 2);
    dataFile.print(",");
    dataFile.print(nir_s, 2);
    dataFile.print(",");
    dataFile.print(nir_t, 2);
    dataFile.print(",");
    dataFile.print(nir_u, 2);
    dataFile.print(",");
    dataFile.print(nir_v, 2);
    dataFile.print(",");
    dataFile.print(nir_w, 2);
    dataFile.print(",");
    
    // LTR390 UV data
    dataFile.print(uv_index, 2);
    dataFile.print(",");
    dataFile.print(uva, 0);
    dataFile.print(",");
    dataFile.println(als, 0);

    dataFile.flush();
    dataFile.close();

    // Also print to serial
    Serial.print(dateStr);
    Serial.print(",");
    Serial.print(timeStr);
    Serial.print(",");
    Serial.print(now.unixtime());
    Serial.print(",");
    Serial.print(as7341_readings[0]);
    Serial.print(",");
    Serial.print(as7341_readings[1]);
    Serial.print(",");
    Serial.print(as7341_readings[2]);
    Serial.print(",");
    Serial.print(as7341_readings[3]);
    Serial.print(",");
    Serial.print(as7341_readings[4]);
    Serial.print(",");
    Serial.print(as7341_readings[5]);
    Serial.print(",");
    Serial.print(as7341_readings[6]);
    Serial.print(",");
    Serial.print(as7341_readings[7]);
    Serial.print(",");
    Serial.print(as7341_readings[9]);
    Serial.print(",");
    Serial.print(as7341_readings[10]);
    Serial.print(",");
    Serial.print(lux_visible, 2);
    Serial.print(",");
    Serial.print(lux_ir, 2);
    Serial.print(",");
    Serial.print(nir_r, 2);
    Serial.print(",");
    Serial.print(nir_s, 2);
    Serial.print(",");
    Serial.print(nir_t, 2);
    Serial.print(",");
    Serial.print(nir_u, 2);
    Serial.print(",");
    Serial.print(nir_v, 2);
    Serial.print(",");
    Serial.print(nir_w, 2);
    Serial.print(",");
    Serial.print(uv_index, 2);
    Serial.print(",");
    Serial.print(uva, 0);
    Serial.print(",");
    Serial.println(als, 0);
    
  } else {
    Serial.println("FAILED - No UV data available");
  }
}
