# -*- coding: utf-8 -*-
"""
# Project: MIRACA
# License: MIT License
# Copyright (c) 2024 miracaEU Contributors
# See LICENSE file for details.
"""

import os
import pandas as pd
import glob

# Get the current working directory
current_folder = os.getcwd()


""" 1. Display results """


def case_study_results(analysis=None):
    """
    Load and summarize DC OPF case study results.
    
    Parameters
    ----------
    analysis : str or None
        One of {"lower", "middle", "upper", "SPOF"} to load a specific file.
        If None or invalid, falls back to scanning all DC_OPF_results*.xlsx.
    """

    # Map analysis keywords to filenames
    lookup = {
        "lower": "DC_OPF_results_lower_Sava.xlsx",
        "middle": "DC_OPF_results_middle_Sava.xlsx",
        "upper": "DC_OPF_results_upper_Sava.xlsx",
        "spof": "DC_OPF_results_SPOF.xlsx",
    }

    # Normalize argument
    chosen = str(analysis).lower() if analysis is not None else None

    # --- CASE 1: Valid specific choice ---------------------------------------
    if chosen in lookup:
        file_path = os.path.join(current_folder, lookup[chosen])

        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Requested analysis='{analysis}', but file not found:\n  {file_path}"
            )

        dc_opf_results_df = pd.read_excel(file_path)

    # --- CASE 2: No / invalid argument → fallback to original behavior -------
    else:
        files = glob.glob(os.path.join(current_folder, "*DC_OPF_results*.xlsx"))

        if not files:
            raise FileNotFoundError(
                "No Excel files with 'DC_OPF_results' found in the folder."
            )

        # Use the first matching file (original behavior)
        file_path = files[0]
        dc_opf_results_df = pd.read_excel(file_path)

    # --- Print summary ------------------------------------------------------
    print()
    print("Case study disruption results:")
    print(f"Loaded file: {os.path.basename(file_path)}")
    print()

    print(
        "Total generator costs:",
        round(dc_opf_results_df["total_gen_costs (€)"].sum() / 1e6, 2),
        "million €",
    )
    print(
        "Maximum line loading percent:",
        round(dc_opf_results_df["max_line_loading (%)"].max(), 2),
        "%",
    )

    #Commented these out as they currently only print 0
    #print("Overloaded lines:", int(dc_opf_results_df.overloaded_lines.sum()))
    #print("Number of affected buses:", int(dc_opf_results_df.affected_buses.sum()))
    #print("Direct economic losses:", round(dc_opf_results_df["direct_losses (million €)"].sum(), 2), "million €",)

    print(
        "Indirect losses:",
        round(dc_opf_results_df["indirect_losses (million €)"].sum(), 2),
        "million €",
    )
    print(
        "Energy not supplied:",
        round(
            dc_opf_results_df["total_load_ref (MW)"].sum()
            - dc_opf_results_df["total_load_res (MW)"].sum(),
            2,
        ),
        "MWh",
    )


""" 2 Check and save disconnected elements """


def disconnected_elements(net):

    print(
        "Number of disconnected buses:", len(net.bus.loc[~net.bus["in_service"]].index)
    )
    print(
        "Number of disconnected lines:",
        len(net.line.loc[~net.line["in_service"]].index),
    )
    print(
        "Number of disconnected loads:",
        len(net.load.loc[~net.load["in_service"]].index),
    )
    print(
        "Number of disconnected generators:",
        len(net.gen.loc[~net.gen["in_service"]].index),
    )

    bus_df = net.line.loc[~net.line["in_service"]].copy()
    bus_df["element_type"] = "bus"

    line_df = net.line.loc[~net.line["in_service"]].copy()
    line_df["element_type"] = "line"

    load_df = net.load[~net.load["in_service"]].copy()
    load_df["element_type"] = "load"

    gen_df = net.gen[~net.gen["in_service"]].copy()
    gen_df["element_type"] = "gen"

    # Concatenate them into one DataFrame
    combined_df = pd.concat([bus_df, line_df, load_df, gen_df], ignore_index=True)

    disconnected_lines = net.line[~net.line["in_service"]]
    voltage_counts = disconnected_lines["voltage"].value_counts()
    print()
    print("Disconnected Lines by voltage level:")
    print(voltage_counts)

    disconnected_buses = net.bus[~net.bus["in_service"]]
    voltage_counts = disconnected_buses["vn_kv"].value_counts()
    print()
    print("Disconnected Buses by voltage level:")
    print(voltage_counts)

    disconnected_gens = net.gen[net.gen["bus"].isin(disconnected_buses.index)]

    print()
    print("Number of generators on disconnected buses:")
    print(disconnected_gens.name)

    #change to False to avoid saving a list of the disconnected elements to Excel
    save_disconnected_elements = True

    if save_disconnected_elements is True:
        combined_df.to_excel(
            "Disconnected_elements_from_DC_OPF_results.xlsx", index=False
        )
    else:
        None


""" 3 Diagnostics of the disruption """


def disruption_diagnostics(net):

    print(
        "Disconnected loads percentage of the total load:",
        round(net.load.loc[~net.load["in_service"]].load_factor.sum() * 100, 2),
    )
    print(
        "Disconnected gens percentage of the total nominal power:",
        round(
            net.gen[~net.gen["in_service"]].p_mw.sum() / net.gen.p_mw.sum() * 100,
            2,
        ),
    )
    print(
        "Disconnected buses percentage of the total buses:",
        round(len(net.bus[~net.bus["in_service"]]) / len(net.bus) * 100, 2),
    )
    print(
        "Disconnected lines percentage of the total lines:",
        round(len(net.line[~net.line["in_service"]]) / len(net.line) * 100, 2),
    )
