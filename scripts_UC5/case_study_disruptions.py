# -*- coding: utf-8 -*-
"""
# Project: MIRACA
# License: MIT License
# Copyright (c) 2024 miracaEU Contributors
# See LICENSE file for details.
"""
import os
import sys
import geopandas as gpd
from pathlib import Path
from UC5_disruption_flooding_events import (
    targeted_disruption,
    plot_affected_regions,
    plot_historical_affected_regions,
    plot_disabled_elements,
    plot_power_flow_static,
)

if __name__ == "__main__":
    current_folder = Path(__file__).resolve().parent
    sys.path.append(str(current_folder))


""" Plotting historically affected regions """


def get_area(folder_basename, countries_to_filter):
    """Get disruption area geometry"""

    # Check if rivers_gdf is already in memory
    if "rivers_gdf" in globals():
        print("Using existing rivers_gdf from memory.")

    # If not in memory, check if it's cached on disk
    elif os.path.exists(f"{folder_basename}//geodata_files//rivers_sava_filtered.gpkg"):
        #print("Loading rivers_gdf from local cache...")
        rivers_gdf = gpd.read_file(
            f"{folder_basename}//geodata_files//rivers_sava_filtered.gpkg"
        )
    else:
        print("No data found. Move rivers_sava_filtered.gpkg to geodata_files.")
        sys.exit()

    sava_gdf = rivers_gdf[rivers_gdf["name"].str.lower() == "sava"]

    sava_lines = sava_gdf[sava_gdf.geometry.geom_type == "LineString"].copy()
    sava_lines.reset_index(drop=True, inplace=True)
    return sava_lines, rivers_gdf


def plot_regions(folder_basename, countries_to_filter):
    """Plot historically affected region"""
    sava_lines, rivers_gdf = get_area(folder_basename, countries_to_filter)

    target_rivers = [
        "sava",
        "tržiška bistrica",
        "kokra",
        "sora",
        "ljubljanica",
        "kamniška bistrica",
        "savinja",
        "mirna",
        "krka",
        "sotla",
    ]

    filtered_rivers_gdf = rivers_gdf[
        rivers_gdf["name"].str.lower().isin(target_rivers)
    ]

    filtered_rivers_gdf = filtered_rivers_gdf[
        filtered_rivers_gdf.geometry.geom_type == "LineString"
    ].copy()
    filtered_rivers_gdf.reset_index(drop=True, inplace=True)

    affected_polygons = plot_historical_affected_regions(
        filtered_rivers_gdf, countries_to_filter, "tributaries", show_plot=True
    )


def create_disruption(
    net,
    folder_basename,
    countries_to_filter,
    automatic=False,
    elements="nodes",
    region="upper",
    buffer=5,
):
    """
    Simulates a disruption in a specified region of the power network.

    Parameters
    ----------
    net : pandapowerNet
        The Pandapower network object containing buses, loads, generators, and other elements.
    automatic : bool, optional
        If True, the disruption is generated automatically based on predefined function.
        If False, manual intervention or specification is required. Default is False.
    elements : str, optional
        The type of network elements to be affected by the disruption.
        Possible inputs: "nodes" or "generators". Default is "nodes".
    region : str, optional
        The geographical or logical region within the network where the disruption will occur.
        Possible inputs include "upper", "lower", "middle". Default is "upper".
    buffer : int or float, optional
        A numerical value representing the buffer zone around the region of disruption.
        This can be used to expand the affected area. Default is 5 (km).

    Returns
    -------
    None
        This function modifies the input network in-place and does not return a value.
    """

    if automatic:
        disruption = "True"
    else:
        # Prompt the user for disruption event for case study scenario
        disruption = input(
            "Do you want to simulate the case study disruption (True/False): "
        )

    if disruption.lower() == "true":

        sava_lines, rivers_gdf = get_area(folder_basename, countries_to_filter)

        target_rivers = [
            "sava",
            "tržiška bistrica",
            "kokra",
            "sora",
            "ljubljanica",
            "kamniška bistrica",
            "savinja",
            "mirna",
            "krka",
            "sotla",
        ]

        filtered_rivers_gdf = rivers_gdf[
            rivers_gdf["name"].str.lower().isin(target_rivers)
        ]

        filtered_rivers_gdf = filtered_rivers_gdf[
            filtered_rivers_gdf.geometry.geom_type == "LineString"
        ].copy()
        filtered_rivers_gdf.reset_index(drop=True, inplace=True)

        affected_polygons = plot_historical_affected_regions(
            filtered_rivers_gdf, countries_to_filter, "tributaries"
        )

        """ x.2 Calling function - UC5 disruptions and importing targeted_disruption """
        if automatic:
            target_elements = elements
        else:
            # Chose targeted elements: nodes or generators
            target_elements = input(
                "Which elements to target in flooding event (generators/nodes): "
            )

        if (target_elements != "generators") & (target_elements != "nodes"):
            target_elements = "generators"

        if automatic:
            target_region = region
            target_buffer = buffer
        else:
            target_region = input(
                "Choose the target region in a major flooding event: (upper/middle/lower) or (all) for whole Sava River Corridor: "
            )
            target_buffer = float(
                input(
                    "Choose the target buffer zone in a major flooding event: (0.5/1/3/5) in km: "
                )
            )

        if target_region.lower() == "upper":
            region_geo = affected_polygons["Radovljica"]
        elif target_region.lower() == "middle":
            region_geo = affected_polygons["Litija"]
        elif target_region.lower() == "lower":
            region_geo = affected_polygons["Čatež ob Savi"]
        else:
            region_geo = sava_lines

        distruption = targeted_disruption(
            net=net,
            net_type="electrical",
            region_geo=region_geo,
            targeted_elements=target_elements,
            buffer=target_buffer * 1000,
        )

        affected_nodes_geodata = distruption[0]
        affected_connections_geodata = distruption[1]

        if target_elements == "nodes":
            plot_affected_regions(
                net=net,
                place=sava_lines,
                nodes=affected_nodes_geodata,
                connections=affected_connections_geodata,
                countries=countries_to_filter,
                type_="nodes",
            )
        else:
            plot_affected_regions(
                net=net,
                place=sava_lines,
                nodes=affected_nodes_geodata,
                connections=affected_connections_geodata,
                countries=countries_to_filter,
                type_="generators",
            )

        """ x.3 Reasign the slack generator """
        if target_elements == "nodes":
            # Step 1: Get IDs of in-service buses
            in_service_buses = net.bus[net.bus["in_service"]].index

            # Step 2: Identify valid generators (connected to in-service buses)
            valid_gens = net.gen[net.gen["bus"].isin(in_service_buses)]

            # Step 3: Identify invalid generators (connected to out-of-service buses)
            invalid_gens = net.gen[~net.gen["bus"].isin(in_service_buses)]

            # Step 4: Set invalid generators to inactive and uncontrollable
            net.gen.loc[invalid_gens.index, ["in_service", "controllable"]] = [
                False,
                False,
            ]

            # Step 5: Find the best generator among valid ones
            if not valid_gens.empty:
                best_gen_idx = valid_gens["max_p_mw"].idxmax()
                best_gen = net.gen.loc[best_gen_idx]
                net.gen.at[best_gen_idx, "slack"] = True
                print(
                    f"Best generator index: {best_gen_idx}, max_p_mw: {best_gen['max_p_mw']}"
                )
            else:
                print("No generators connected to in-service buses.")

            # Step 6: Identify invalid loads (connected to out-of-service buses)
            invalid_loads = net.load[~net.load["bus"].isin(in_service_buses)]

            # Step 7: Set invalid loads to inactive
            net.load.loc[invalid_loads.index, ["in_service"]] = [False]

        else:
            valid_gens = net.gen[net.gen.in_service]
            best_gen_idx = valid_gens["max_p_mw"].idxmax()
            best_gen = net.gen.loc[best_gen_idx]
            net.gen.at[best_gen_idx, "slack"] = True
            print(
                f"Best generator index: {best_gen_idx}, max_p_mw: {best_gen['max_p_mw']}"
            )


""" Combine and export the disruption simulation results """


def combine_res_and_export(
    pf_results_before, pf_results_after, title, pd, load_profiles
):
    pf_results = (
        pd.concat([pf_results_before, pf_results_after], axis=0)
        .sort_values("time_step")
        .reset_index(drop=True)
    )

    # Reset index of load_profiles to make 'utc_timestamp' a column
    load_profiles_reset = load_profiles.reset_index()

    # Merge on matching dates
    merged_df = pd.merge(
        pf_results,
        load_profiles_reset,
        left_on="time_step",
        right_on="utc_timestamp",
        how="inner",  # or 'outer' if you want all dates
    )

    # Export results
    merged_df.to_excel(title, index=False)


def run_predefined_simulation(
    net,
    folder_basename,
    countries_to_filter,
    pd,
    load_profiles,
    pf_res_plotly,
    time_series_calculations,
    regions="all",
    disrupted_node_names=None,
):
    if regions == "upper":

        time_series_short = load_profiles[0:36]

        pf_results_before = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Baseline power flow before interruption")

        # UC5 simulation through the sava river time-dependant flow
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="upper",
            buffer=5,
        )

        
        # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
        apply_node_outage_by_name(net, disrupted_node_names)

        #plot_disabled_elements(net)

        # Upper sava river - 2017 example - using existing load profiles
        time_series_short = load_profiles[
            36:
        ]  # First 36 hours of the month and the rest days period

        pf_results_after = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        # Export resuts
        combine_res_and_export(
            pf_results_before,
            pf_results_after,
            "DC_OPF_results_upper_Sava.xlsx",
            pd,
            load_profiles,
        )

    elif regions == "middle":

        time_series_short = load_profiles[0:24]

        pf_results_before = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Baseline power flow before interruption")

        # UC5 simulation through the sava river time-dependant flow
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="middle",
            buffer=5,
        )

        # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
        apply_node_outage_by_name(net, disrupted_node_names)

        #plot_disabled_elements(net)

        # Middle sava  - 2023 example
        time_series_short = load_profiles[24:]

        pf_results_after = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        # Export results
        combine_res_and_export(
            pf_results_before,
            pf_results_after,
            "DC_OPF_results_middle_Sava.xlsx",
            pd,
            load_profiles,
        )

    elif regions == "lower":

        # Lower region - 2023 flooding - using 2020 data
        time_series_short = load_profiles[0:48]

        pf_results_before = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Baseline power flow before interruption")

        # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
        apply_node_outage_by_name(net, disrupted_node_names)

        #plot_disabled_elements(net)

        # UC5 simulation through the sava river time-dependant flow
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="lower",
            buffer=5,
        )

        # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
        apply_node_outage_by_name(net, disrupted_node_names)

        #plot_disabled_elements(net)

        # Lower sava  - 2023 example
        time_series_short = load_profiles[48:]

        pf_results_after = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        # Export results
        combine_res_and_export(
            pf_results_before,
            pf_results_after,
            "DC_OPF_results_lower_Sava.xlsx",
            pd,
            load_profiles,
        )
    else:
        """UC5 simulation through the sava river time-dependant flow"""
        time_series_short = load_profiles[0:12]

        pf_results_before = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Baseline power flow before interruption")

        # 1. Upper region
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="upper",
            buffer=5,
        )

        # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
        apply_node_outage_by_name(net, disrupted_node_names)

        #plot_disabled_elements(net)

        time_series_short = load_profiles[12:24]

        pf_results_1 = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        # 2. Middle region
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="middle",
            buffer=5,
        )
        time_series_short = load_profiles[24:48]

        pf_results_2 = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        # 3. Lower region
        create_disruption(
            net,
            folder_basename,
            countries_to_filter,
            automatic=True,
            elements="nodes",
            region="lower",
            buffer=5,
        )
        time_series_short = load_profiles[48:]

        pf_results_3 = time_series_calculations(time_series_short, net, "DC OPF")
        #pf_res_plotly(net)
        # Static counterpart of the interactive plot above — renders on GitHub
        # and in the Jupyter Book (see plot_power_flow_static docstring).
        plot_power_flow_static(net, title="Rerouted power flow during the disruption")

        pf_results = (
            pd.concat([pf_results_1, pf_results_2, pf_results_3], axis=0)
            .sort_values("time_step")
            .reset_index(drop=True)
        )

        combine_res_and_export(
            pf_results_before, pf_results, "DC_OPF_results_Sava_all.xlsx"
        )

def apply_node_outage_by_name(net, node_names, verbose=True):
    """
    Disables one or more buses by their names and updates connected elements.
    This mirrors the logic you use after a node-based flooding disruption
    (e.g., deactivating generators/loads on out-of-service buses and reassigning a slack generator).

    Parameters
    ----------
    net : pandapowerNet
        The pandapower network
    node_names : str | list[str] | None
        One or multiple bus names to disable. Case-insensitive.
    verbose : bool
        If True, prints what was disabled and replacement slack info.
    """
    if node_names is None:
        return

    # Normalize to list
    if isinstance(node_names, str):
        node_names = [node_names]
    else:
        try:
            node_names = list(node_names)
        except TypeError:
            node_names = [node_names]

    if not node_names:
        return

    # Ensure the 'name' column exists
    if "name" not in net.bus.columns:
        raise ValueError("net.bus has no 'name' column to match bus names against.")

    # Case-insensitive matching
    wanted = {str(n).lower() for n in node_names}
    mask = net.bus["name"].astype(str).str.lower().isin(wanted)
    target_buses = net.bus.index[mask]

    if len(target_buses) == 0:
        if verbose:
            print(f"[apply_node_outage_by_name] No buses found with names: {node_names}")
        return

    # Disable the target buses
    net.bus.loc[target_buses, "in_service"] = False


    # Recompute in-service buses after disabling
    in_service_buses = set(net.bus.index[net.bus["in_service"]])

    # Helper to deactivate single-bus elements
    def _deactivate_single_bus_elements(df_name, also_set=None):
        if not hasattr(net, df_name):
            return
        df = getattr(net, df_name)
        if "bus" not in df.columns:
            return
        invalid = df.index[~df["bus"].isin(in_service_buses)]
        if len(invalid):
            df.loc[invalid, "in_service"] = False
            if also_set:
                for col, val in also_set.items():
                    if col in df.columns:
                        df.loc[invalid, col] = val

    # Helper to deactivate two-bus elements (lines) or transformers
    def _deactivate_two_bus_elements(df_name, bus_cols):
        if not hasattr(net, df_name):
            return
        df = getattr(net, df_name)
        if not all(col in df.columns for col in bus_cols):
            return
        invalid = df.index[~df[bus_cols[0]].isin(in_service_buses) |
                           ~df[bus_cols[1]].isin(in_service_buses)]
        if len(invalid):
            df.loc[invalid, "in_service"] = False

    # Single-bus elements
    _deactivate_single_bus_elements("gen", also_set={"controllable": False})
    _deactivate_single_bus_elements("sgen")
    _deactivate_single_bus_elements("load")
    _deactivate_single_bus_elements("ward")
    _deactivate_single_bus_elements("xward")
    _deactivate_single_bus_elements("shunt")
    _deactivate_single_bus_elements("storage")
    _deactivate_single_bus_elements("ext_grid")  # slacks

    # Two-bus elements
    _deactivate_two_bus_elements("line", ["from_bus", "to_bus"])
    _deactivate_two_bus_elements("trafo", ["hv_bus", "lv_bus"])
    # For 3W transformers, you could disable if any of the three buses is down:
    if hasattr(net, "trafo3w"):
        df = net.trafo3w
        if all(col in df.columns for col in ["hv_bus", "mv_bus", "lv_bus"]):
            invalid = df.index[
                ~df["hv_bus"].isin(in_service_buses) |
                ~df["mv_bus"].isin(in_service_buses) |
                ~df["lv_bus"].isin(in_service_buses)
            ]
            if len(invalid):
                df.loc[invalid, "in_service"] = False

    # Reassign a slack generator like your existing pattern (when nodes are targeted)
    # 1) Get in-service buses again (post element updates)
    in_service_buses = net.bus[net.bus["in_service"]].index

    # 2) Valid generators = those on in-service buses
    if hasattr(net, "gen") and "bus" in net.gen.columns:
        valid_gens = net.gen[net.gen["bus"].isin(in_service_buses)]
        invalid_gens = net.gen[~net.gen["bus"].isin(in_service_buses)]
        if len(invalid_gens):
            net.gen.loc[invalid_gens.index, ["in_service", "controllable"]] = [False, False]

        # 3) Set new slack (your existing approach)
        if not valid_gens.empty:
            best_gen_idx = valid_gens["max_p_mw"].idxmax()
            # ensure 'slack' exists
            if "slack" not in net.gen.columns:
                net.gen["slack"] = False
            net.gen["slack"] = False
            net.gen.at[best_gen_idx, "slack"] = True
            if verbose:
                print(f"[apply_node_outage_by_name] New slack generator index: {best_gen_idx}, "
                      f"max_p_mw: {net.gen.at[best_gen_idx, 'max_p_mw']}")
        else:
            if verbose:
                print("[apply_node_outage_by_name] No generators connected to in-service buses.")

    # 4) Also deactivate loads on out-of-service buses (if any remain)
    if hasattr(net, "load") and "bus" in net.load.columns:
        invalid_loads = net.load[~net.load["bus"].isin(in_service_buses)]
        if len(invalid_loads):
            net.load.loc[invalid_loads.index, "in_service"] = False



def single_point_of_failure(
    net,
    folder_basename,
    countries_to_filter,
    pd,
    load_profiles,
    pf_res_plotly,
    time_series_calculations,
    regions="all",
    disrupted_node_names=None,
):

    time_series_short = load_profiles[0:36]

    pf_results_before = time_series_calculations(time_series_short, net, "DC OPF")

    #enable all nodes and edges in the network for consitent plotting
    enable_all_elements(net) 
    
    #pf_res_plotly(net)
    # Static counterpart of the interactive plot above — renders on GitHub
    # and in the Jupyter Book (see plot_power_flow_static docstring).
    plot_power_flow_static(net, title="Baseline power flow before interruption")

    # Optional manual node disruptions (by bus name) — applied in addition to the flooding disruption
    apply_node_outage_by_name(net, disrupted_node_names)

    plot_disabled_elements(net)

    # Upper sava river - 2017 example - using existing load profiles
    time_series_short = load_profiles[
        36:
    ]  # First 36 hours of the month and the rest days period

    pf_results_after = time_series_calculations(time_series_short, net, "DC OPF")
    #pf_res_plotly(net)
    # Static counterpart of the interactive plot above — renders on GitHub
    # and in the Jupyter Book (see plot_power_flow_static docstring).
    plot_power_flow_static(net, title="Rerouted power flow during the disruption")

    # Export resuts
    combine_res_and_export(
        pf_results_before,
        pf_results_after,
        "DC_OPF_results_SPOF.xlsx",
        pd,
        load_profiles,
    )


def enable_all_elements(net, verbose=True):
    """
    Enables all nodes (buses) and all edges (lines, transformers),
    as well as loads, generators, and all other elements in a pandapower network.
    """
    # 1. Enable all buses (nodes)
    if verbose: 
        net.bus["in_service"] = True

    # 2. Enable all lines (edges)
    if verbose: 
        net.line["in_service"] = True

    # 3. Enable all transformers
    if hasattr(net, "trafo"):
        if verbose: 
            net.trafo["in_service"] = True

    if hasattr(net, "trafo3w"):
        if verbose:     
            net.trafo3w["in_service"] = True

    # 4. Enable all loads & generation units
    if hasattr(net, "load"):
        net.load["in_service"] = True
    if hasattr(net, "sgen"):
        net.sgen["in_service"] = True
    if hasattr(net, "gen"):
        net.gen["in_service"] = True
    if hasattr(net, "ext_grid"):
        net.ext_grid["in_service"] = True
    if hasattr(net, "shunt"):
        net.shunt["in_service"] = True
    if hasattr(net, "storage"):
        net.storage["in_service"] = True
