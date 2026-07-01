# -*- coding: utf-8 -*-
"""
# Project: MIRACA
# License: MIT License
# Copyright (c) 2024 miracaEU Contributors
# See LICENSE file for details.
"""

import os
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pandas as pd
import geopandas as gpd
import pickle
from shapely.ops import unary_union
from shapely.geometry import LineString

# Get the current working directory
current_folder = os.getcwd()


def targeted_disruption(net, net_type, region_geo, targeted_elements, buffer=1000):
    """
    Parameters
    ----------
    net : pandapower network object

    net_type : string
        Choose either electrical or gas.
    region_geo : pd.DataFrame
        geographical data of the analysed region.
    targeted_elements : string
        Choose either nodes or generators.
    buffer : int, optional
        set buffer in meters. The default is 1 km. Flooding in critical ares can be 3-5 km.

    Returns
    -------
    affected_nodes_geodata: pd.DataFrame

    affected_connections_geodata: pd.DataFrame

    """
    if net_type == "electrical":
        net_node_geodata = net.bus_geodata
        net_connection_geodata = net.line_geodata
        net_node = net.bus
        net_connection = net.line
        from_node = "from_bus"
        to_node = "to_bus"

    elif net_type == "gas":
        net_node_geodata = net.junction_geodata
        net_connection_geodata = net.pipe_geodata
        net_node = net.junction
        net_connection = net.pipe
        from_node = "from_junction"
        to_node = "to_junction"

    else:
        return print("Choose valid network type: (electrical or gas)")

    region_geo = gpd.GeoDataFrame(
        region_geo, geometry=region_geo.geometry, crs="EPSG:4326"
    )
    # 1. Project to a metric CRS (e.g., EPSG:3857)
    region_projected = region_geo.to_crs(epsg=3857)

    # 2. Create a buffer
    buffer = region_projected.buffer(buffer)

    # 3. Project your nodes to the same CRS
    net_geodata = gpd.GeoDataFrame(
        net_node_geodata, geometry="geometry", crs="EPSG:4326"
    )
    net_geodata_projected = net_geodata.to_crs(epsg=3857)
    buffer_union = unary_union(buffer)

    # Now apply the mask
    node_mask = net_geodata_projected.geometry.apply(
        lambda point: buffer_union.contains(point)
    )

    # Get affected nodes IDs
    affected_nodes = net_node.loc[node_mask].index
    print("affected nodes:")
    print(affected_nodes)

    if targeted_elements == "nodes":
        # Disable affected junctions
        net_node.loc[node_mask, "in_service"] = False

        # Disable connections to affected nodes
        connection_mask = net_connection[from_node].isin(
            affected_nodes
        ) | net_connection[to_node].isin(affected_nodes)
        net_connection.loc[connection_mask, "in_service"] = False

        # Get affected nodes IDs
        affected_connections = net_connection.loc[connection_mask].index

        # Return the affected elements geodata
        affected_nodes_geodata = net_node_geodata[
            net_node_geodata.index.isin(affected_nodes)
        ]
        affected_connections_geodata = net_connection_geodata[
            net_connection_geodata.index.isin(affected_connections)
        ]
        disconnected_nodes = net_node.loc[~net_node["in_service"]].index
        disconnected_connections = net_connection.loc[
            ~net_connection["in_service"]
        ].index

        affected_nodes_geodata = net_node_geodata[
            net_node_geodata.index.isin(disconnected_nodes)
        ]
        affected_connections_geodata = net_connection_geodata[
            net_connection_geodata.index.isin(disconnected_connections)
        ]

    elif targeted_elements == "generators":
        gen_mask = net.gen["bus"].isin(affected_nodes)
        net.gen.loc[gen_mask, "in_service"] = False
        net.gen.loc[gen_mask, "controllable"] = False

        # Identify affected nodes (connected to out of service generators)
        affected_nodes = net.gen.loc[~net.gen["in_service"]].bus

        # Identify affected nodes geodata
        affected_nodes_geodata = net.bus_geodata[
            net.bus_geodata.index.isin(affected_nodes)
        ]

        # Create empty dataframe
        affected_connections_geodata = pd.DataFrame(columns=["name", "coords"])
    else:
        return print("Choose valid targeted elements")

    return affected_nodes_geodata, affected_connections_geodata


def plot_affected_regions(net, place, nodes, connections, countries, type_):
    from shapely.geometry import LineString

    all_nodes = gpd.GeoDataFrame(
        net.bus_geodata, geometry=net.bus_geodata.geometry, crs="EPSG:4326"
    )

    all_connections = [
        LineString(coord_list) for coord_list in net.line_geodata["coords"]
    ]
    all_connections = gpd.GeoDataFrame(
        all_connections, geometry=all_connections, crs="EPSG:4326"
    )

    # Get boundaries for each country and concatenate into one GeoDataFrame
    country = pd.read_pickle(f"{current_folder}//inputs//pickle_files//country.pkl")

    nodes = gpd.GeoDataFrame(nodes, geometry=nodes.geometry, crs="EPSG:4326")

    # Convert coords to LineString geometries
    connections_geometry = [
        LineString(coord_list) for coord_list in connections["coords"]
    ]

    # Create GeoDataFrame
    connections = gpd.GeoDataFrame(
        connections, geometry=connections_geometry, crs="EPSG:4326"
    )

    # Set up the plot
    fig, ax = plt.subplots(figsize=(12, 10))

    # Plot place boundaries
    country.boundary.plot(ax=ax, color="black", linewidth=1)

    # Plot the place
    place.plot(ax=ax, color="blue", linewidth=2, label="Sava River")

    if type_ == "nodes":
        all_nodes.plot(ax=ax, color="grey", label="Connected Nodes")
        # Plot the disconnected nodes
        nodes.plot(ax=ax, color="red", label="Disconnected Nodes")
    else:
        all_nodes.plot(ax=ax, color="grey", label="Not Affected Nodes")
        # Plot the disconnected nodes
        nodes.plot(ax=ax, color="red", label="Affected Nodes")

    all_connections.plot(ax=ax, color="grey", markersize=50, label="Connected Lines")

    # Plot the affected connections
    if not connections.empty:
        connections.plot(ax=ax, color="red", markersize=50, label="Disconnected Lines")

    # Add labels and legend
    ax.set_title(
        "Affected Regions and Infrastructure Following the Disruption", fontsize=14
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend()

    # Optional: Add grid and improve layout
    ax.grid(True)
    plt.tight_layout()

    # Show the plot
    plt.show()



def plot_disabled_elements(net):
    """
    Plot disabled vs active nodes and edges in a pandapower network.
    
    Disabled nodes/lines appear in RED.
    Active nodes/lines appear in GREY.
    """

    # --- Nodes ---------------------------------------------------------------
    if net.bus_geodata.empty:
        raise ValueError("net.bus_geodata is empty — cannot plot node geodata.")
    
    nodes_all = gpd.GeoDataFrame(
        net.bus_geodata.copy(),
        geometry=net.bus_geodata.geometry,
        crs="EPSG:4326"
    )

    # Add service status for filtering
    nodes_all["in_service"] = net.bus["in_service"].values
    nodes_active = nodes_all[nodes_all["in_service"] == True]
    nodes_disabled = nodes_all[nodes_all["in_service"] == False]

    # --- Lines ---------------------------------------------------------------
    if net.line_geodata.empty:
        raise ValueError("net.line_geodata is empty — cannot plot line geodata.")

    # Convert line coords to LineString
    all_line_geoms = [
        LineString(coords) for coords in net.line_geodata["coords"]
    ]

    lines_all = gpd.GeoDataFrame(
        net.line_geodata.copy(),
        geometry=all_line_geoms,
        crs="EPSG:4326"
    )

    # Add service status
    lines_all["in_service"] = net.line["in_service"].values
    lines_active = lines_all[lines_all["in_service"] == True]
    lines_disabled = lines_all[lines_all["in_service"] == False]

    # --- Plotting ------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 10))

    # Get boundaries for each country and concatenate into one GeoDataFrame
    country = pd.read_pickle(f"{current_folder}//inputs//pickle_files//country.pkl")

    # Plot place boundaries
    country.boundary.plot(ax=ax, color="black", linewidth=1)

    # Active lines (grey)
    if not lines_active.empty:
        lines_active.plot(ax=ax, color="grey", linewidth=1, label="Active Lines")

    # Disabled lines (red)
    if not lines_disabled.empty:
        lines_disabled.plot(ax=ax, color="red", linewidth=1.8, label="Disabled Lines")

    # Active nodes (grey)
    if not nodes_active.empty:
        nodes_active.plot(ax=ax, color="grey", markersize=20, label="Active Nodes")

    # Disabled nodes (red)
    if not nodes_disabled.empty:
        nodes_disabled.plot(ax=ax, color="red", markersize=30, label="Disabled Nodes")

    # Formatting
    ax.set_title(
        "Affected Regions and Infrastructure Following the Disruption", fontsize=14
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.show()


def plot_historical_affected_regions(sava_lines, countries, rivers, show_plot=False):

    # Get boundaries for each country and concatenate into one GeoDataFrame
    country = pd.read_pickle(f"{current_folder}//inputs//pickle_files//country.pkl")

    with open(f"{current_folder}//inputs//pickle_files//affected_polygons.pkl", "rb") as f:
        affected_polygons = pickle.load(f)

    # Step 2: Plot the river and affected regions
    fig, ax = plt.subplots(figsize=(12, 10))

    # Plot place boundaries
    country.boundary.plot(ax=ax, color="black", linewidth=1)

    # Plot Sava River
    if rivers == "sava":
        sava_lines.plot(ax=ax, color="blue", linewidth=2, label="Sava River")
    else:
        sava_lines.plot(
            ax=ax, color="blue", linewidth=2, label="Sava River with Its Tributaries"
        )

    # Plot affected regions with numbered labels
    for i, (label, gdf) in enumerate(affected_polygons.items(), start=1):
        if label == "Radovljica":
            time = "1926"
        elif label == "Čatež ob Savi":
            time = "2010"
        elif label == "Litija":
            time = "2023"
        for geom in gdf.geometry:
            if geom.geom_type == "Polygon":
                x, y = geom.exterior.xy
                ax.plot(x, y, color="red", linewidth=2, label=f"{i}. {label}, {time}")
                # Add number label at centroid
                centroid = geom.centroid
                ax.text(
                    centroid.x,
                    centroid.y,
                    str(i),
                    fontsize=12,
                    color="black",
                    weight="bold",
                )

    if rivers == "sava":
        plt.title("Sava River and Historically Flood-Affected Regions in Slovenia")
    else:
        plt.title(
            "Sava River with Its Tributaries and Historically Flood-Affected Regions in Slovenia"
        )

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.tight_layout()
    if show_plot == True:
        plt.show()

    plt.close()

    return affected_polygons


def plot_power_flow_static(
    net,
    title="Power Flow Simulation Results",
    v_min=0.9,
    v_max=1.1,
    load_min=0,
    load_max=100,
    cmap="jet",
):
    """
    Static (matplotlib) map of the current power-flow state.

    Buses are coloured by their per-unit voltage (``net.res_bus.vm_pu``) and
    active lines by their loading (``net.res_line.loading_percent``), both on a
    blue->red colour map; buses and lines that are out of service
    (disconnected) are drawn in black. The Slovenian country outline is
    included for context, mirroring the "affected regions and infrastructure"
    plots. Two colour bars are shown, matching the interactive
    ``pf_res_plotly`` figure (bus voltage and line loading).

    Unlike ``pf_res_plotly`` (an interactive Plotly figure that only renders in
    front-ends with plotly.js, e.g. VS Code / JupyterLab), this produces a
    static PNG, so the result also shows up on GitHub and in the Jupyter Book
    without any extra configuration.

    Parameters
    ----------
    net : pandapowerNet
        Network with populated ``res_bus`` / ``res_line`` (run a power flow /
        OPF first) and geodata (call ``fix_geodata`` beforehand).
    title : str
        Plot title.
    v_min, v_max : float
        Voltage bounds (p.u.) for the bus colour scale. Default 0.9-1.1,
        matching the interactive ``pf_res_plotly`` colour bar.
    load_min, load_max : float
        Line-loading bounds (%) for the line colour scale. Default 0-100.
    cmap : str
        Matplotlib colormap (default "jet": blue = low, red = high).
    """
    # --- Country outline (same source as the other UC5 map plots) -----------
    country = pd.read_pickle(f"{current_folder}//inputs//pickle_files//country.pkl")

    # --- Bus voltages and disconnection status ------------------------------
    if not net.res_bus.empty and "vm_pu" in net.res_bus.columns:
        vm_pu = net.res_bus["vm_pu"].reindex(net.bus.index)
    else:
        vm_pu = pd.Series(index=net.bus.index, dtype=float)

    has_results = vm_pu.notna().any()

    # A bus is "disconnected" if it is out of service. When power-flow results
    # exist, buses left without a solved voltage (NaN) are treated the same way.
    bus_disconnected = ~net.bus["in_service"].astype(bool)
    if has_results:
        bus_disconnected = bus_disconnected | vm_pu.isna()
    else:
        print(
            "[plot_power_flow_static] No res_bus voltages found - "
            "showing network topology only (run a power flow / OPF first)."
        )
        vm_pu = vm_pu.fillna(1.0)

    geo_idx = net.bus_geodata.index
    connected_idx = net.bus.index[~bus_disconnected].intersection(geo_idx)
    disconnected_idx = net.bus.index[bus_disconnected].intersection(geo_idx)

    # --- Lines: loading (%) and disconnection status ------------------------
    line_geoms = [LineString(coords) for coords in net.line_geodata["coords"]]
    lines_all = gpd.GeoDataFrame(
        net.line_geodata.copy(), geometry=line_geoms, crs="EPSG:4326"
    )
    lines_all["in_service"] = net.line["in_service"].reindex(lines_all.index).values

    if not net.res_line.empty and "loading_percent" in net.res_line.columns:
        lines_all["loading_percent"] = (
            net.res_line["loading_percent"].reindex(lines_all.index).values
        )
    else:
        lines_all["loading_percent"] = float("nan")

    lines_active = lines_all[lines_all["in_service"]].copy()
    lines_disconnected = lines_all[~lines_all["in_service"]]

    # --- Plot ---------------------------------------------------------------
    # Figure aspect chosen to match Slovenia's wide/short footprint so the map
    # fills the axes instead of leaving large empty bands top and bottom.
    fig, ax = plt.subplots(figsize=(12, 7))

    # Country boundary (also fixes the map extent for the collections below)
    country.boundary.plot(ax=ax, color="black", linewidth=1)

    # Active lines coloured by loading (blue -> red). Built as a matplotlib
    # LineCollection (added with autolim=False) rather than geopandas' column
    # plotting, which triggers a transform-recursion crash on matplotlib 3.8.
    line_cl = None
    if not lines_active.empty:
        loading_vals = lines_active["loading_percent"].fillna(0.0).to_numpy()
        segments = [list(geom.coords) for geom in lines_active.geometry]
        line_cl = LineCollection(
            segments,
            cmap=cmap,
            norm=Normalize(vmin=load_min, vmax=load_max),
            linewidths=1.4,
            zorder=1,
        )
        line_cl.set_array(loading_vals)
        ax.add_collection(line_cl, autolim=False)

    # Disconnected lines in black
    if not lines_disconnected.empty:
        dseg = [list(geom.coords) for geom in lines_disconnected.geometry]
        ax.add_collection(
            LineCollection(
                dseg,
                colors="black",
                linewidths=1.6,
                zorder=2,
                label="Disconnected line",
            ),
            autolim=False,
        )

    # Disconnected buses in black
    if len(disconnected_idx) > 0:
        ax.scatter(
            net.bus_geodata.loc[disconnected_idx, "x"],
            net.bus_geodata.loc[disconnected_idx, "y"],
            color="black",
            s=45,
            zorder=3,
            label="Disconnected bus",
        )

    # Connected buses coloured by voltage (blue -> red)
    sc = None
    if len(connected_idx) > 0:
        sc = ax.scatter(
            net.bus_geodata.loc[connected_idx, "x"],
            net.bus_geodata.loc[connected_idx, "y"],
            c=vm_pu.loc[connected_idx],
            cmap=cmap,
            vmin=v_min,
            vmax=v_max,
            s=45,
            edgecolor="black",
            linewidth=0.2,
            zorder=4,
        )

    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True)
    ax.margins(0.02)  # trim padding between the network and the axes frame
    # Let the map fill the axes box (no aspect-driven side gap). The figure size
    # is chosen to match Slovenia's ~1.5:1 footprint, so proportions stay close
    # to geographic without leaving whitespace around the network.
    ax.set_aspect("auto")

    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper right")

    # Two colour bars (bus voltage + line loading), mirroring pf_res_plotly.
    # An axes divider makes each bar exactly as tall as the map without
    # extending the figure; the gap before the second bar leaves room for the
    # first bar's tick labels so the two bars and labels never overlap.
    divider = make_axes_locatable(ax)
    if sc is not None:
        cax_v = divider.append_axes("right", size="3.5%", pad=0.12)
        cbar_v = fig.colorbar(sc, cax=cax_v)
        cbar_v.set_label("Bus Voltage [p.u.]")
    if line_cl is not None:
        cax_l = divider.append_axes("right", size="3.5%", pad=0.8)
        cbar_l = fig.colorbar(line_cl, cax=cax_l)
        cbar_l.set_label("Line Loading [%]")

    plt.show()
