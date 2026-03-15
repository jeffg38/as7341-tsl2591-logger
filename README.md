# AS7341 + TSL2591 + AS726x (IR) + LTR390UV Sensor Logger (full complement of sensors) added to the complete spectral logger Arduino code. Visualization file also updated.

# AS7341 + TSL2591 Sensor Logger

Arduino-based dual sensor data logger combining spectral and lux measurements with timestamp logging.

## Overview

This project logs environmental light data using two complementary sensors:
- **Adafruit AS7341** - 10-channel spectral color sensor (415nm to 910nm)
- **Adafruit TSL2591** - High dynamic range light sensor (lux measurements)

Data is logged to SD card with RTC timestamps for time-series analysis.

## Hardware Requirements

- Adafruit microcontroller board (specify which one you're using - RP2040, KB2040, etc.)
- Adafruit AS7341 11-Channel Spectral Color Sensor
- Adafruit TSL2591 High Dynamic Range Digital Light Sensor
- SD card module
- Real-time clock (RTC) module
- SD card (formatted FAT32)

## Wiring

(Add your specific pin connections here)

## Software Dependencies

Arduino libraries required:
- Adafruit AS7341 library
- Adafruit TSL2591 library
- SD library
- RTClib (if using RTC)
- Wire library

Install via Arduino Library Manager.

## Usage

1. Upload `as7341_tsl2591_logger.ino` to your board
2. Insert formatted SD card
3. Power on - logging begins automatically
4. Data is saved to SD card as CSV files

## Data Visualization

Python script included for plotting spectral and lux data:
```bash
cd visualization
python spectral_plotter_AS7341-TSL2591.py
```

Requirements:
- Python 3.x
- matplotlib
- pandas
- numpy

## Data Format

CSV output includes:
- Timestamp
- 10 spectral channels (415nm, 445nm, 480nm, 515nm, 555nm, 590nm, 630nm, 680nm, clear, NIR)
- Lux measurements
- (Add other fields your logger outputs)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built using Adafruit hardware and libraries.

# as7341-t212591-logger
Adafruit AS7341 spectral sensor and TSL2591 lux sensor data logger with SD card storage
