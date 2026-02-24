# -*- coding: utf-8 -*-
"""
# Project: MIRACA
# License: MIT License
# Copyright (c) 2024 miracaEU Contributors
# See LICENSE file for details.
"""

from shapely.geometry import Point
import geopandas as gpd


def define_interval(load_profiles):
    start_time = "2015-01-01 00:00:00"
    end_time = "2016-01-01 01:00:00"

    # Get the first and last utc_timestamp from the index
    first_timestamp = load_profiles.index[0]  # First value in the index
    last_timestamp = load_profiles.index[-1]  # Last value in the index

    default_time_period = True #set to false to allow for manual setting of the investigated time period

    if default_time_period:
        start_time = "2020-08-01 00:00:00 "
        end_time = "2020-08-08 00:00:00 "
    else:
        print("First UTC Timestamp:\n", first_timestamp)
        print("Last UTC Timestamp:\n", last_timestamp)

        # Define default start and end times
        default_start_time = "2015-01-01 00:00:00"
        default_end_time = "2015-02-01 01:00:00"

        # Prompt the user for start and end times, using defaults if input is empty
        start_time = (
            input(f"Enter the start time (default: '{default_start_time}'): ")
            or default_start_time
        )
        end_time = (
            input(f"Enter the end time (default: '{default_end_time}'): ")
            or default_end_time
        )
        print()

    # Print the selected times
    print("Start time:", start_time)
    print("End time:", end_time)

    return start_time, end_time


def fix_geodata(net):
    # Bus_geodata is containing 'x' and 'y' columns
    buses_geodata = net.bus_geodata
    # Create geometry from x and y columns
    buses_geodata["geometry"] = buses_geodata.apply(
        lambda row: Point(row["x"], row["y"]), axis=1
    )
    # Convert to GeoDataFrame
    buses_geodata = gpd.GeoDataFrame(buses_geodata, geometry="geometry")
    # Set CRS to match the element.geometry CRS (e.g., EPSG:4326 for WGS84)
    buses_geodata = buses_geodata.set_crs("EPSG:4326")
