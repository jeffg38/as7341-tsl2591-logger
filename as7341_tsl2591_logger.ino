/*
 * AS7341 Spectral Sensor + TSL2591 Lux Sensor Data Logger
 * For Adalogger RP2040 with DS3231 RTC and SD card
 * Based on working BME680 datalogger structure
 */

#include <Wire.h>
#include <SPI.h>
#include "SdFat.h"
#include <RTClib.h>
#include <Adafruit_AS7341.h>
#include <Adafruit_TSL2591.h>

// =====================
// Hardware / objects
// =====================
Adafruit_AS7341 as7341;  // I2C AS7341 (spectral sensor)
Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591);  // I2C TSL2591 (lux sensor)
RTC_DS3231 rtc;          // DS3231 RTC

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

// Heartbeat LED - blink once every 10 seconds (same as logging interval)
const unsigned long HEARTBEAT_INTERVAL = 10000;  // Changed from 1000 to 10000
unsigned long lastHeartbeat = 0;
bool ledState = false;

// =====================
// Helper function
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
    dataFile.print("# AS7341 Spectral Logger + TSL2591 Lux Sensor Started: ");
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
    dataFile.println("#");
    
    // Write header with spectral channel names + lux values
    dataFile.println("Date,Time,Time_s,F1_415nm,F2_445nm,F3_480nm,F4_515nm,F5_555nm,F6_590nm,F7_630nm,F8_680nm,NIR,Clear,Lux_Visible,Lux_IR");
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

  Serial.println("\nAS7341 Spectral Logger (Adalogger RP2040)");
  Serial.println("==========================================");

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
    Serial.println("Check wiring/power and I2C address.");
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
    Serial.println("Check wiring and I2C address.");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(200);
      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }
  }
  Serial.println("OK.");

  // Configure AS7341 settings
  as7341.setATIME(100);
  as7341.setASTEP(999);
  as7341.setGain(AS7341_GAIN_0_5X); // direct sunlight 0.5 - 1x, indoor 32X and above to capture dark conditions
  
  Serial.println("AS7341 configured:");
  Serial.println("  ATIME: 100");
  Serial.println("  ASTEP: 999");
  Serial.println("  Gain: 0.5X");

  // ----- TSL2591 -----
  Serial.print("Initializing TSL2591... ");
  if (!tsl.begin()) {
    Serial.println("FAILED!");
    Serial.println("ERROR: TSL2591 not found on I2C!");
    Serial.println("Check wiring and I2C address (should be 0x29).");
    while (1) {
      digitalWrite(LED_BUILTIN, HIGH);
      delay(300);
      digitalWrite(LED_BUILTIN, LOW);
      delay(300);
    }
  }
  Serial.println("OK.");
  
  // Configure TSL2591 settings
  tsl.setGain(TSL2591_GAIN_LOW);       // Medium gain (25x) - good starting point
  tsl.setTiming(TSL2591_INTEGRATIONTIME_100MS);  // 100ms integration
  
  Serial.println("TSL2591 configured:");
  Serial.println("  Gain: LOW (1x)");
  Serial.println("  Integration: 100ms");

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
  Serial.println("==========================================");;
  
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
  
  // Heartbeat LED
  if (currentTime - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    lastHeartbeat = currentTime;
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState);
  }
  
  // Check if it's time to log
  if (currentTime - lastLog < LOG_INTERVAL_MS) return;
  lastLog = currentTime;

  // Read AS7341 spectral data
  uint16_t readings[12];
  if (!as7341.readAllChannels(readings)) {
    Serial.println("WARNING: AS7341 reading failed, skipping.");
    return;
  }

  // Read TSL2591 lux values
  uint32_t lum = tsl.getFullLuminosity();
  uint16_t ir = lum >> 16;
  uint16_t full = lum & 0xFFFF;
  
  // Calculate visible lux (IR-compensated)
  float lux_visible = tsl.calculateLux(full, ir);
  
  // Calculate IR lux estimate
  // The IR channel reads infrared, we can estimate IR "lux" using the same scaling
  // Note: This isn't standard "lux" (which is for visible light), but gives IR intensity
  float lux_ir = 0.0;
  if (ir > 0) {
    // Use similar calculation as visible lux but for IR channel
    // Scale based on gain and integration time
    uint16_t gain_val = 1;
    switch(tsl.getGain()) {
      case TSL2591_GAIN_LOW:  gain_val = 1; break;
      case TSL2591_GAIN_MED:  gain_val = 25; break;
      case TSL2591_GAIN_HIGH: gain_val = 428; break;
      case TSL2591_GAIN_MAX:  gain_val = 9876; break;
    }
    
    uint16_t time_val = 100;  // Default 100ms
    switch(tsl.getTiming()) {
      case TSL2591_INTEGRATIONTIME_100MS: time_val = 100; break;
      case TSL2591_INTEGRATIONTIME_200MS: time_val = 200; break;
      case TSL2591_INTEGRATIONTIME_300MS: time_val = 300; break;
      case TSL2591_INTEGRATIONTIME_400MS: time_val = 400; break;
      case TSL2591_INTEGRATIONTIME_500MS: time_val = 500; break;
      case TSL2591_INTEGRATIONTIME_600MS: time_val = 600; break;
    }
    
    // IR lux estimate (arbitrary scaling to make values reasonable)
    lux_ir = ((float)ir / ((float)gain_val * (float)time_val / 100.0)) * 0.46;
  }

  // Timestamp
  DateTime now = rtc.now();
  char dateStr[11]; // YYYY-MM-DD
  char timeStr[9];  // HH:MM:SS
  snprintf(dateStr, sizeof(dateStr), "%04d-%02d-%02d", now.year(), now.month(), now.day());
  snprintf(timeStr, sizeof(timeStr), "%02d:%02d:%02d", now.hour(), now.minute(), now.second());

  // Open file and write data
  dataFile = SD.open(filename, FILE_WRITE);
  if (!dataFile) {
    Serial.println("ERROR: Could not open log file!");
    return;
  }

  // Write: Date, Time, Time_s, F1-F8, NIR, Clear, Lux_Visible, Lux_IR
  dataFile.print(dateStr);
  dataFile.print(",");
  dataFile.print(timeStr);
  dataFile.print(",");
  dataFile.print(now.unixtime());
  dataFile.print(",");
  dataFile.print(readings[0]);  // F1 - 415nm
  dataFile.print(",");
  dataFile.print(readings[1]);  // F2 - 445nm
  dataFile.print(",");
  dataFile.print(readings[2]);  // F3 - 480nm
  dataFile.print(",");
  dataFile.print(readings[3]);  // F4 - 515nm
  dataFile.print(",");
  dataFile.print(readings[4]);  // F5 - 555nm
  dataFile.print(",");
  dataFile.print(readings[5]);  // F6 - 590nm
  dataFile.print(",");
  dataFile.print(readings[6]);  // F7 - 630nm
  dataFile.print(",");
  dataFile.print(readings[7]);  // F8 - 680nm
  dataFile.print(",");
  dataFile.print(readings[9]);  // NIR
  dataFile.print(",");
  dataFile.print(readings[10]); // Clear
  dataFile.print(",");
  dataFile.print(lux_visible, 2);  // Visible lux (2 decimal places)
  dataFile.print(",");
  dataFile.println(lux_ir, 2);     // IR lux estimate (2 decimal places)

  dataFile.flush();
  dataFile.close();

  // Also print to serial
  Serial.print(dateStr);
  Serial.print(",");
  Serial.print(timeStr);
  Serial.print(",");
  Serial.print(now.unixtime());
  Serial.print(",");
  Serial.print(readings[0]);
  Serial.print(",");
  Serial.print(readings[1]);
  Serial.print(",");
  Serial.print(readings[2]);
  Serial.print(",");
  Serial.print(readings[3]);
  Serial.print(",");
  Serial.print(readings[4]);
  Serial.print(",");
  Serial.print(readings[5]);
  Serial.print(",");
  Serial.print(readings[6]);
  Serial.print(",");
  Serial.print(readings[7]);
  Serial.print(",");
  Serial.print(readings[9]);
  Serial.print(",");
  Serial.print(readings[10]);
  Serial.print(",");
  Serial.print(lux_visible, 2);
  Serial.print(",");
  Serial.println(lux_ir, 2);
}
