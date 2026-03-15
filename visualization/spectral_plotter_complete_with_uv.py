#!/usr/bin/env python3
"""
Complete Spectral + UV Plotter
AS7341 + TSL2591 + AS7263 + LTR390
Plots all spectral measurements, lux values, and UV data over time with night shading

Usage:
    # Plot all CSV files in a folder:
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files
    
    # Plot a single file:
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files/SPECLOGG.CSV
    
    # With options:
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files --ymax 15000
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import os
import argparse
from pathlib import Path
import glob
import math

# Parse command line arguments
parser = argparse.ArgumentParser(
    description='Plot complete spectral + UV data from all sensors',
    epilog='''Examples:
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files/SPECLOGG.CSV
    python3 spectral_plotter_complete_with_uv.py Data_Logger_Files --ymax 15000
    '''
)
parser.add_argument('path', 
                    help='Path to CSV file or directory containing CSV files')
parser.add_argument('--ymin', type=float, default=None,
                    help='Minimum y-axis value for AS7341 (default: auto-scale)')
parser.add_argument('--ymax', type=float, default=None,
                    help='Maximum y-axis value for AS7341 (default: auto-scale)')
parser.add_argument('--xmin', type=str, default=None,
                    help='Start date/time for x-axis (format: "YYYY-MM-DD HH:MM:SS")')
parser.add_argument('--xmax', type=str, default=None,
                    help='End date/time for x-axis (format: "YYYY-MM-DD HH:MM:SS")')
parser.add_argument('--title', type=str, default=None,
                    help='Plot title (default: auto-generated from filename)')

args = parser.parse_args()

# Determine if path is a file or directory
input_path = Path(args.path)

# Get list of CSV files to process
csv_files = []

if input_path.is_file():
    # Single file
    if input_path.suffix.lower() == '.csv':
        csv_files = [input_path]
    else:
        print(f"Error: {input_path} is not a CSV file")
        exit(1)
elif input_path.is_dir():
    # Directory - find all CSV files
    csv_files = sorted(input_path.glob('*.csv')) + sorted(input_path.glob('*.CSV'))
    if not csv_files:
        print(f"Error: No CSV files found in {input_path}")
        exit(1)
else:
    print(f"Error: Path not found: {input_path}")
    exit(1)

print(f"\n{'='*70}")
print(f"COMPLETE SPECTRAL + UV PLOTTER - Processing {len(csv_files)} file(s)")
print(f"{'='*70}\n")

def plot_csv_file(csv_path, args):
    """Plot a single CSV file with all sensors including LTR390 UV"""
    
    print(f"\n{'─'*70}")
    print(f"Processing: {csv_path.name}")
    print(f"{'─'*70}")
    
    # Check if file exists
    if not csv_path.exists():
        print(f"  ✗ File not found: {csv_path}")
        return False
    
    try:
        # Read the CSV file, skipping comment lines
        df = pd.read_csv(csv_path, comment='#')
        print(f"  ✓ Read {len(df)} measurements")
        
    except Exception as e:
        print(f"  ✗ Error reading file: {e}")
        return False
    
    # Combine Date and Time columns into a datetime object
    try:
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    except Exception as e:
        print(f"  ✗ Error parsing dates: {e}")
        return False
    
    # Get data time range
    data_start = df['DateTime'].min()
    data_end = df['DateTime'].max()
    print(f"  ✓ Time range: {data_start} to {data_end}")
    
    # Parse x-axis limits if provided
    xmin_dt = None
    xmax_dt = None
    if args.xmin:
        try:
            xmin_dt = pd.to_datetime(args.xmin)
        except Exception as e:
            print(f"  ✗ Error parsing --xmin: {e}")
            return False
    
    if args.xmax:
        try:
            xmax_dt = pd.to_datetime(args.xmax)
        except Exception as e:
            print(f"  ✗ Error parsing --xmax: {e}")
            return False
    
    # Determine the plot time range
    plot_start = xmin_dt if xmin_dt is not None else data_start
    plot_end = xmax_dt if xmax_dt is not None else data_end
    
    # Calculate sunrise and sunset times for Denver, CO
    # Denver: 39.7392°N, 104.9903°W
    # Timezone: Mountain Time (UTC-7 in winter, UTC-6 in summer/DST)
    lat = 39.7392
    lon = -104.9903
    
    # Get unique dates in the dataset
    unique_dates = df['DateTime'].dt.date.unique()
    
    sunrise_times = []
    sunset_times = []
    
    def calculate_sunrise_sunset(date, lat, lon):
        """
        Calculate sunrise and sunset using Jean Meeus algorithm
        Simplified but accurate to within 2 minutes
        """
        # Day of year
        N = date.timetuple().tm_yday
        
        # Fractional year in radians
        gamma = 2 * math.pi / 365 * (N - 1)
        
        # Equation of time (minutes)
        eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                          - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
        
        # Solar declination (radians)
        decl = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) \
               - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma) \
               - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
        
        # Time offset (minutes)
        time_offset = eqtime + 4 * lon
        
        # Hour angle (degrees)
        lat_rad = math.radians(lat)
        
        # cos(hour_angle) for sunrise/sunset
        # Using -0.833 degrees for atmospheric refraction
        cos_ha = (math.cos(math.radians(90.833)) - math.sin(lat_rad) * math.sin(decl)) / \
                 (math.cos(lat_rad) * math.cos(decl))
        
        # Check if sun rises/sets
        if cos_ha > 1 or cos_ha < -1:
            return None, None
        
        # Hour angle in degrees
        ha = math.degrees(math.acos(cos_ha))
        
        # Sunrise and sunset in UTC (minutes from midnight)
        sunrise_utc = 720 - 4 * ha - time_offset
        sunset_utc = 720 + 4 * ha - time_offset
        
        # Determine timezone offset
        # DST starts second Sunday in March (March 9, 2026)
        # DST ends first Sunday in November
        year = date.year
        month = date.month
        day = date.day
        
        # Simple DST check for 2026
        if month > 3 and month < 11:
            tz_offset = -6 * 60  # MDT (UTC-6)
        elif month == 3 and day >= 9:  # DST starts March 9, 2026
            tz_offset = -6 * 60  # MDT
        elif month == 11 and day < 2:  # Approximate - DST ends early Nov
            tz_offset = -6 * 60  # MDT
        else:
            tz_offset = -7 * 60  # MST (UTC-7)
        
        # Convert UTC to local time by ADDING the offset (offset is negative)
        sunrise_minutes = sunrise_utc + tz_offset
        sunset_minutes = sunset_utc + tz_offset
        
        # Handle day boundaries
        if sunrise_minutes < 0:
            sunrise_minutes += 1440
        if sunset_minutes >= 1440:
            sunset_minutes -= 1440
        
        # Convert to datetime
        sunrise_hour = int(sunrise_minutes / 60)
        sunrise_min = int(sunrise_minutes % 60)
        sunset_hour = int(sunset_minutes / 60)
        sunset_min = int(sunset_minutes % 60)
        
        sunrise_dt = datetime.combine(date, datetime.min.time()) + timedelta(hours=sunrise_hour, minutes=sunrise_min)
        sunset_dt = datetime.combine(date, datetime.min.time()) + timedelta(hours=sunset_hour, minutes=sunset_min)
        
        return sunrise_dt, sunset_dt
    
    for date in unique_dates:
        try:
            sr, ss = calculate_sunrise_sunset(date, lat, lon)
            
            if sr is not None and ss is not None:
                if plot_start <= sr <= plot_end:
                    sunrise_times.append(sr)
                if plot_start <= ss <= plot_end:
                    sunset_times.append(ss)
    
        except Exception as e:
            pass  # Skip if can't calculate
    
    # Auto-generate title from filename if not specified
    if args.title:
        plot_title = args.title
    else:
        base_name = csv_path.stem
        plot_title = f'Complete Spectral + UV Data: {base_name}'
    
    # Define AS7341 channels with wavelengths and colors
    as7341_channels = {
        'F1_415nm': {'wavelength': 415, 'color': '#4B0082', 'label': 'F1 (415nm Violet)'},
        'F2_445nm': {'wavelength': 445, 'color': '#0000FF', 'label': 'F2 (445nm Blue)'},
        'F3_480nm': {'wavelength': 480, 'color': '#00BFFF', 'label': 'F3 (480nm Cyan)'},
        'F4_515nm': {'wavelength': 515, 'color': '#00FF00', 'label': 'F4 (515nm Green)'},
        'F5_555nm': {'wavelength': 555, 'color': '#7FFF00', 'label': 'F5 (555nm Yellow-Green)'},
        'F6_590nm': {'wavelength': 590, 'color': '#FFFF00', 'label': 'F6 (590nm Yellow)'},
        'F7_630nm': {'wavelength': 630, 'color': '#FF8C00', 'label': 'F7 (630nm Orange)'},
        'F8_680nm': {'wavelength': 680, 'color': '#FF0000', 'label': 'F8 (680nm Red)'},
        'NIR_910nm': {'wavelength': 910, 'color': '#000000', 'label': 'NIR (910nm)'},
    }
    
    # Define AS7263 NIR channels with wavelengths and colors
    as7263_channels = {
        'R_610nm': {'wavelength': 610, 'color': '#8B0000', 'label': 'R (610nm Deep Red)'},
        'S_680nm': {'wavelength': 680, 'color': '#DC143C', 'label': 'S (680nm Red)'},
        'T_730nm': {'wavelength': 730, 'color': '#8B4513', 'label': 'T (730nm Far-Red)'},
        'U_760nm': {'wavelength': 760, 'color': '#A0522D', 'label': 'U (760nm NIR)'},
        'V_810nm': {'wavelength': 810, 'color': '#D2691E', 'label': 'V (810nm NIR)'},
        'W_860nm': {'wavelength': 860, 'color': '#CD853F', 'label': 'W (860nm NIR)'},
    }
    
    # Create figure with 4 subplots
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(16, 18), sharex=True)
    
    # ========================================
    # SUBPLOT 1: AS7341 Spectral Channels
    # ========================================
    for channel, info in as7341_channels.items():
        if channel in df.columns:
            ax1.plot(df['DateTime'], df[channel],
                    color=info['color'],
                    label=info['label'],
                    linewidth=2,
                    alpha=0.8)
    
    ax1.set_ylabel('AS7341 Intensity (counts)', fontsize=12, fontweight='bold')
    ax1.set_title(plot_title, fontsize=14, fontweight='bold', pad=20)
    
    if args.ymin is not None or args.ymax is not None:
        ymin = args.ymin if args.ymin is not None else ax1.get_ylim()[0]
        ymax = args.ymax if args.ymax is not None else ax1.get_ylim()[1]
        ax1.set_ylim(ymin, ymax)
    
    ax1.grid(True, which='major', alpha=0.3, linestyle='--')
    ax1.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)
    ax1.legend(loc='best', fontsize=8, framealpha=0.9, ncol=3)
    
    # ========================================
    # SUBPLOT 2: AS7263 NIR Channels
    # ========================================
    has_as7263 = all(ch in df.columns for ch in as7263_channels.keys())
    
    if has_as7263:
        for channel, info in as7263_channels.items():
            ax2.plot(df['DateTime'], df[channel],
                    color=info['color'],
                    label=info['label'],
                    linewidth=2.5,
                    alpha=0.85)
        
        ax2.set_ylabel('AS7263 NIR (calibrated)', fontsize=12, fontweight='bold')
        ax2.grid(True, which='major', alpha=0.3, linestyle='--')
        ax2.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)
        ax2.legend(loc='best', fontsize=9, framealpha=0.9, ncol=2)
    else:
        ax2.text(0.5, 0.5, 'No AS7263 NIR data available', 
                 ha='center', va='center', fontsize=14, transform=ax2.transAxes)
        ax2.set_ylabel('AS7263 NIR (Not Available)', fontsize=12, fontweight='bold')
    
    # ========================================
    # SUBPLOT 3: TSL2591 Lux Values
    # ========================================
    has_lux = 'Lux_Visible' in df.columns and 'Lux_IR' in df.columns
    
    if has_lux:
        ax3.plot(df['DateTime'], df['Lux_Visible'],
                 color='#FFD700', linewidth=2.5, label='Lux (Visible)', alpha=0.9)
        
        ax3_ir = ax3.twinx()
        ax3_ir.plot(df['DateTime'], df['Lux_IR'],
                    color='#8B0000', linewidth=2.5, label='Lux (IR)', alpha=0.9, linestyle='--')
        
        ax3.set_ylabel('Visible Lux', fontsize=12, fontweight='bold', color='#FFD700')
        ax3_ir.set_ylabel('IR Lux', fontsize=12, fontweight='bold', color='#8B0000')
        ax3.tick_params(axis='y', labelcolor='#FFD700')
        ax3_ir.tick_params(axis='y', labelcolor='#8B0000')
        
        ax3.grid(True, which='major', alpha=0.3, linestyle='--')
        ax3.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)
        
        lines1, labels1 = ax3.get_legend_handles_labels()
        lines2, labels2 = ax3_ir.get_legend_handles_labels()
        ax3.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=10, framealpha=0.9)
    else:
        ax3.text(0.5, 0.5, 'No Lux data available', 
                 ha='center', va='center', fontsize=14, transform=ax3.transAxes)
        ax3.set_ylabel('Lux (Not Available)', fontsize=12, fontweight='bold')
    
    # ========================================
    # SUBPLOT 4: LTR390 UV Data (NEW!)
    # ========================================
    has_uv = 'UV_Index' in df.columns and 'UVA' in df.columns
    
    if has_uv:
        # UV Index on left axis
        ax4.plot(df['DateTime'], df['UV_Index'],
                 color='#9370DB', linewidth=3, label='UV Index', alpha=0.95, marker='o', markersize=3)
        
        # Add UV Index reference zones
        ax4.axhspan(0, 2, alpha=0.1, color='green', label='Low (0-2)')
        ax4.axhspan(3, 5, alpha=0.1, color='yellow', label='Moderate (3-5)')
        ax4.axhspan(6, 7, alpha=0.1, color='orange', label='High (6-7)')
        ax4.axhspan(8, 10, alpha=0.1, color='red', label='Very High (8-10)')
        ax4.axhspan(11, 20, alpha=0.1, color='purple', label='Extreme (11+)')
        
        ax4.set_ylabel('UV Index', fontsize=12, fontweight='bold', color='#9370DB')
        ax4.tick_params(axis='y', labelcolor='#9370DB')
        ax4.set_ylim(0, max(12, df['UV_Index'].max() * 1.1))  # Scale to data, min 12
        
        # UVA raw counts on right axis
        ax4_uva = ax4.twinx()
        ax4_uva.plot(df['DateTime'], df['UVA'],
                     color='#FF6347', linewidth=2, label='UVA (counts)', alpha=0.85, linestyle='--')
        
        ax4_uva.set_ylabel('UVA Raw Counts', fontsize=12, fontweight='bold', color='#FF6347')
        ax4_uva.tick_params(axis='y', labelcolor='#FF6347')
        
        ax4.grid(True, which='major', alpha=0.3, linestyle='--')
        ax4.grid(True, which='minor', alpha=0.2, linestyle='--', linewidth=0.5)
        
        # Combine legends
        lines1, labels1 = ax4.get_legend_handles_labels()
        lines2, labels2 = ax4_uva.get_legend_handles_labels()
        ax4.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9, framealpha=0.9, ncol=2)
    else:
        ax4.text(0.5, 0.5, 'No LTR390 UV data available', 
                 ha='center', va='center', fontsize=14, transform=ax4.transAxes)
        ax4.set_ylabel('UV Data (Not Available)', fontsize=12, fontweight='bold')
    
    # Set x-axis limits
    ax1.set_xlim(plot_start, plot_end)
    
    # ========================================
    # Add Night Shading and Sunrise/Sunset Lines
    # ========================================
    # Create night periods (sunset to sunrise)
    night_periods = []
    
    # Sort sunrise and sunset times
    all_sunrises = sorted(sunrise_times)
    all_sunsets = sorted(sunset_times)
    
    # Add night period before first sunrise if needed
    if all_sunrises and plot_start < all_sunrises[0]:
        night_periods.append((plot_start, all_sunrises[0]))
    
    # Add night periods between sunset and next sunrise
    for i, ss in enumerate(all_sunsets):
        if i < len(all_sunrises):
            if i + 1 < len(all_sunrises):
                night_periods.append((ss, all_sunrises[i + 1]))
            else:
                if ss < plot_end:
                    night_periods.append((ss, plot_end))
    
    # Add night period after last sunset if needed
    if all_sunsets and all_sunsets[-1] < plot_end:
        if not all_sunrises or all_sunsets[-1] > all_sunrises[-1]:
            night_periods.append((all_sunsets[-1], plot_end))
    
    # Shade night periods on all subplots
    for ax in [ax1, ax2, ax3, ax4]:
        for night_start, night_end in night_periods:
            ax.axvspan(night_start, night_end, alpha=0.15, color='navy', zorder=0)
    
    # Add sunrise and sunset vertical lines
    for ax in [ax1, ax2, ax3, ax4]:
        for sr in sunrise_times:
            ax.axvline(x=sr, color='orange', linestyle='-', linewidth=2, alpha=0.7, zorder=5)
            ypos = ax.get_ylim()[1] * 0.95
            ax.text(sr, ypos, 'Sunrise', rotation=90, verticalalignment='top',
                    horizontalalignment='right', fontsize=9, fontweight='bold', 
                    color='orange', zorder=6)
    
        for ss in sunset_times:
            ax.axvline(x=ss, color='darkblue', linestyle='-', linewidth=2, alpha=0.7, zorder=5)
            ypos = ax.get_ylim()[1] * 0.95
            ax.text(ss, ypos, 'Sunset', rotation=90, verticalalignment='top',
                    horizontalalignment='right', fontsize=9, fontweight='bold',
                    color='darkblue', zorder=6)
    
    # Format x-axis
    ax4.set_xlabel('Date and Time', fontsize=12, fontweight='bold')
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M:%S'))
    ax4.xaxis.set_major_locator(mdates.AutoDateLocator())
    
    ax1.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    ax3.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    ax4.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    # Save the figure in the same directory as the CSV file
    output_filename = f'spectral_plot_complete_uv_{csv_path.stem}.png'
    output_path = csv_path.parent / output_filename
    
    try:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Plot saved: {output_path}")
    except Exception as e:
        print(f"  ✗ Error saving plot: {e}")
        plt.close('all')
        return False
    
    # Print brief statistics
    print(f"  ✓ Data points: {len(df)}")
    if has_lux:
        print(f"  ✓ Avg Lux: {df['Lux_Visible'].mean():.0f} (Visible), {df['Lux_IR'].mean():.0f} (IR)")
    if has_uv:
        max_uv = df['UV_Index'].max()
        avg_uv = df[df['UV_Index'] > 0]['UV_Index'].mean() if (df['UV_Index'] > 0).any() else 0
        print(f"  ✓ UV Index: Max={max_uv:.1f}, Avg={avg_uv:.1f} (when >0)")
    
    plt.close('all')
    return True

# Process all CSV files
success_count = 0
fail_count = 0

for csv_file in csv_files:
    if plot_csv_file(csv_file, args):
        success_count += 1
    else:
        fail_count += 1

# Summary
print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"  ✓ Successfully plotted: {success_count} file(s)")
if fail_count > 0:
    print(f"  ✗ Failed: {fail_count} file(s)")
print(f"{'='*70}\n")
