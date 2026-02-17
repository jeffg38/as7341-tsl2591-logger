#!/usr/bin/env python3
"""
AS7341 Spectral Data + TSL2591 Lux Plotter
Plots spectral measurements and lux values over time

Usage:
    python3 spectral_plotter.py                    # Auto-scale y-axis
    python3 spectral_plotter.py --ymax 10000       # Set max y-axis to 10000
    python3 spectral_plotter.py --ymin 0 --ymax 10000  # Set both min and max
    python3 spectral_plotter.py --title "My Custom Title" --ymax 10000
    python3 spectral_plotter.py --xmin "2025-02-03 16:00:00" --xmax "2025-02-03 20:00:00"
    python3 spectral_plotter.py --xmin "2025-02-03 16:00:00" --xmax "2025-02-03 20:00:00" --ymax 10000 --title "Evening Data"
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import os
import argparse
from astral import LocationInfo
from astral.sun import sun
import pytz

# ===== CONFIGURATION =====
# Set your data directory here
DATA_DIR = 'Data_Logger_Files'
CSV_FILENAME = 'speclog.csv'  # Changed to match AS7341 logger output
DEFAULT_TITLE = 'AS7341 Spectral Data + TSL2591 Lux - Multi-Channel Measurements Over Time'
# =========================

# Parse command line arguments
parser = argparse.ArgumentParser(description='Plot AS7341 spectral data with customizable y-axis range')
parser.add_argument('--ymin', type=float, default=None,
                    help='Minimum y-axis value (default: auto-scale)')
parser.add_argument('--ymax', type=float, default=None,
                    help='Maximum y-axis value (default: auto-scale)')
parser.add_argument('--xmin', type=str, default=None,
                    help='Start date/time for x-axis (format: "YYYY-MM-DD HH:MM:SS")')
parser.add_argument('--xmax', type=str, default=None,
                    help='End date/time for x-axis (format: "YYYY-MM-DD HH:MM:SS")')
parser.add_argument('--title', type=str, default=DEFAULT_TITLE,
                    help=f'Plot title (default: "{DEFAULT_TITLE}")')
parser.add_argument('--data-dir', type=str, default=DATA_DIR,
                    help=f'Path to data directory (default: {DATA_DIR})')
parser.add_argument('--csv-file', type=str, default=CSV_FILENAME,
                    help=f'CSV filename (default: {CSV_FILENAME})')

args = parser.parse_args()

# Use command line arguments if provided
DATA_DIR = args.data_dir
CSV_FILENAME = args.csv_file

# Construct full path to CSV file
csv_path = os.path.join(DATA_DIR, CSV_FILENAME)

# Check if file exists
if not os.path.exists(csv_path):
    print(f"Error: File not found at {csv_path}")
    print("Please check the DATA_DIR path in the script.")
    exit(1)

print(f"Reading data from: {csv_path}")

# Read the CSV file, skipping comment lines (lines starting with #)
df = pd.read_csv(csv_path, comment='#')

# Combine Date and Time columns into a datetime object
df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])

# Get data time range
data_start = df['DateTime'].min()
data_end = df['DateTime'].max()

# Parse x-axis limits if provided
xmin_dt = None
xmax_dt = None
if args.xmin:
    try:
        xmin_dt = pd.to_datetime(args.xmin)
        print(f"X-axis start set to: {xmin_dt}")
    except Exception as e:
        print(f"Error parsing --xmin: {e}")
        print('Use format: "YYYY-MM-DD HH:MM:SS"')
        exit(1)

if args.xmax:
    try:
        xmax_dt = pd.to_datetime(args.xmax)
        print(f"X-axis end set to: {xmax_dt}")
    except Exception as e:
        print(f"Error parsing --xmax: {e}")
        print('Use format: "YYYY-MM-DD HH:MM:SS"')
        exit(1)

# Determine the plot time range
plot_start = xmin_dt if xmin_dt is not None else data_start
plot_end = xmax_dt if xmax_dt is not None else data_end

# Calculate sunrise and sunset times for Denver, CO
denver = LocationInfo("Denver", "USA", "America/Denver", 39.7392, -104.9903)
denver_tz = pytz.timezone('America/Denver')

# Get unique dates in the dataset
unique_dates = df['DateTime'].dt.date.unique()

sunrise_times = []
sunset_times = []

for date in unique_dates:
    try:
        s = sun(denver.observer, date=date, tzinfo=denver_tz)
        # Convert to timezone-naive datetime (remove timezone info for matplotlib compatibility)
        sr = s['sunrise'].replace(tzinfo=None)
        ss = s['sunset'].replace(tzinfo=None)

        # Only add sunrise/sunset if they fall within the plot time range
        if plot_start <= sr <= plot_end:
            sunrise_times.append(sr)
        if plot_start <= ss <= plot_end:
            sunset_times.append(ss)

    except Exception as e:
        print(f"Warning: Could not calculate sun times for {date}: {e}")

print(f"\nSunrise/Sunset times for Denver, CO (Mountain Time) within plot range:")
for sr in sunrise_times:
    print(f"  {sr.date()}: Sunrise {sr.strftime('%H:%M:%S')}")
for ss in sunset_times:
    print(f"  {ss.date()}: Sunset {ss.strftime('%H:%M:%S')}")

# Define the channels with their wavelengths and colors
channels = {
    'F1_415nm': {'wavelength': 415, 'color': '#4B0082', 'label': 'F1 (415nm - Violet)'},
    'F2_445nm': {'wavelength': 445, 'color': '#0000FF', 'label': 'F2 (445nm - Blue)'},
    'F3_480nm': {'wavelength': 480, 'color': '#00BFFF', 'label': 'F3 (480nm - Cyan)'},
    'F4_515nm': {'wavelength': 515, 'color': '#00FF00', 'label': 'F4 (515nm - Green)'},
    'F5_555nm': {'wavelength': 555, 'color': '#7FFF00', 'label': 'F5 (555nm - Yellow-Green)'},
    'F6_590nm': {'wavelength': 590, 'color': '#FFFF00', 'label': 'F6 (590nm - Yellow)'},
    'F7_630nm': {'wavelength': 630, 'color': '#FF8C00', 'label': 'F7 (630nm - Orange)'},
    'F8_680nm': {'wavelength': 680, 'color': '#FF0000', 'label': 'F8 (680nm - Red)'},
    'NIR': {'wavelength': 910, 'color': '#000000', 'label': 'NIR (~910nm - Near Infrared)'},
}

# Create the plot with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)

# ========================================
# SUBPLOT 1: Spectral Channels
# ========================================
# Plot each channel with its corresponding color (lines only, no markers)
for channel, info in channels.items():
    ax1.plot(df['DateTime'], df[channel],
            color=info['color'],
            label=info['label'],
            linewidth=2,
            alpha=0.8)

# Format the spectral plot
ax1.set_ylabel('Intensity (counts)', fontsize=12, fontweight='bold')
ax1.set_title(args.title, fontsize=14, fontweight='bold', pad=20)

# Set y-axis limits if specified
if args.ymin is not None or args.ymax is not None:
    ymin = args.ymin if args.ymin is not None else ax1.get_ylim()[0]
    ymax = args.ymax if args.ymax is not None else ax1.get_ylim()[1]
    ax1.set_ylim(ymin, ymax)
    print(f"Spectral y-axis range set to: {ymin} - {ymax}")

# Add grid
ax1.grid(True, which='major', alpha=0.3, linestyle='--')
ax1.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)

# Add legend
ax1.legend(loc='best', fontsize=9, framealpha=0.9, ncol=2)

# ========================================
# SUBPLOT 2: Lux Values (if available)
# ========================================
# Check if Lux columns exist in the dataframe
has_lux = 'Lux_Visible' in df.columns and 'Lux_IR' in df.columns

if has_lux:
    # Plot visible lux
    ax2.plot(df['DateTime'], df['Lux_Visible'],
             color='#FFD700', linewidth=2.5, label='Lux (Visible)', alpha=0.9)
    
    # Plot IR lux on secondary y-axis
    ax2_ir = ax2.twinx()
    ax2_ir.plot(df['DateTime'], df['Lux_IR'],
                color='#8B0000', linewidth=2.5, label='Lux (IR)', alpha=0.9, linestyle='--')
    
    # Format lux plot
    ax2.set_ylabel('Visible Lux', fontsize=12, fontweight='bold', color='#FFD700')
    ax2_ir.set_ylabel('IR Lux', fontsize=12, fontweight='bold', color='#8B0000')
    ax2.tick_params(axis='y', labelcolor='#FFD700')
    ax2_ir.tick_params(axis='y', labelcolor='#8B0000')
    
    # Add grid
    ax2.grid(True, which='major', alpha=0.3, linestyle='--')
    ax2.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)
    
    # Combine legends
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_ir.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=10, framealpha=0.9)
else:
    # If no lux data, just show a message
    ax2.text(0.5, 0.5, 'No Lux data available in CSV file', 
             ha='center', va='center', fontsize=14, transform=ax2.transAxes)
    ax2.set_ylabel('Lux (Not Available)', fontsize=12, fontweight='bold')

# Set x-axis limits based on data range (unless user specified otherwise)
ax1.set_xlim(plot_start, plot_end)

# Add sunrise and sunset lines to both subplots
for ax in [ax1, ax2]:
    for i, sr in enumerate(sunrise_times):
        ax.axvline(x=sr, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
        # Add text label above the line
        ypos = ax.get_ylim()[1] * 0.95  # Position at 95% of y-axis height
        ax.text(sr, ypos, 'Sunrise', rotation=90, verticalalignment='top',
                horizontalalignment='right', fontsize=9, fontweight='bold')

    for i, ss in enumerate(sunset_times):
        ax.axvline(x=ss, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
        # Add text label above the line
        ypos = ax.get_ylim()[1] * 0.95  # Position at 95% of y-axis height
        ax.text(ss, ypos, 'Sunset', rotation=90, verticalalignment='top',
                horizontalalignment='right', fontsize=9, fontweight='bold')

# Format x-axis to show dates nicely (on bottom subplot only)
ax2.set_xlabel('Date and Time', fontsize=12, fontweight='bold')

# Major ticks - automatic based on data range
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M:%S'))
ax2.xaxis.set_major_locator(mdates.AutoDateLocator())

# Minor ticks - every hour
ax1.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
ax2.xaxis.set_minor_locator(mdates.HourLocator(interval=1))

plt.xticks(rotation=45, ha='right')

# Add grid for major ticks (existing dashed lines)
ax.grid(True, which='major', alpha=0.3, linestyle='--')

# Add grid for minor ticks (hourly dashed lines)
ax.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)

# Add legend
ax.legend(loc='best', fontsize=9, framealpha=0.9)

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the figure in the same directory as the data
output_path = os.path.join(DATA_DIR, 'spectral_plot.png')
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"Plot saved as '{output_path}'")

# Display the plot
plt.show()

# Print some statistics
print("\nData Summary:")
print(f"Total measurements: {len(df)}")
print(f"Time range: {df['DateTime'].min()} to {df['DateTime'].max()}")
print(f"\nChannel Statistics:")
for channel in channels.keys():
    if channel in df.columns:
        print(f"{channel}: min={df[channel].min()}, max={df[channel].max()}, mean={df[channel].mean():.1f}")

# Print lux statistics if available
if has_lux:
    print(f"\nLux Statistics:")
    print(f"Lux_Visible: min={df['Lux_Visible'].min():.2f}, max={df['Lux_Visible'].max():.2f}, mean={df['Lux_Visible'].mean():.2f}")
    print(f"Lux_IR: min={df['Lux_IR'].min():.2f}, max={df['Lux_IR'].max():.2f}, mean={df['Lux_IR'].mean():.2f}")
    if df['Lux_Visible'].mean() > 0:
        print(f"Average IR/Visible Ratio: {(df['Lux_IR'].mean() / df['Lux_Visible'].mean() * 100):.2f}%")

# Close the plot and exit cleanly
plt.close('all')
print("\nScript completed successfully.")
