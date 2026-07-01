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
    total_gen_costs = dc_opf_results_df["total_gen_costs (€)"].sum() / 1e6
    max_line_loading = dc_opf_results_df["max_line_loading (%)"].max()
    indirect_losses = dc_opf_results_df["indirect_losses (million €)"].sum()
    energy_not_supplied = (
        dc_opf_results_df["total_load_ref (MW)"].sum()
        - dc_opf_results_df["total_load_res (MW)"].sum()
    )

    print(f"Case study results  ({os.path.basename(file_path)})")
    print(f"  Total generator costs : {total_gen_costs:7.2f} million €")
    print(f"  Max line loading      : {max_line_loading:7.2f} %")
    print(f"  Indirect losses       : {indirect_losses:7.2f} million €")
    print(f"  Energy not supplied   : {energy_not_supplied:7.2f} MWh")


""" 2 Check and save disconnected elements """


def disconnected_elements(net):

    disconnected_buses = net.bus[~net.bus["in_service"]]
    disconnected_lines = net.line[~net.line["in_service"]]
    disconnected_loads = net.load[~net.load["in_service"]]
    disconnected_gens = net.gen[~net.gen["in_service"]]

    # Build the export table (one row per disconnected element)
    bus_df = net.line.loc[~net.line["in_service"]].copy()
    bus_df["element_type"] = "bus"

    line_df = net.line.loc[~net.line["in_service"]].copy()
    line_df["element_type"] = "line"

    load_df = net.load[~net.load["in_service"]].copy()
    load_df["element_type"] = "load"

    gen_df = net.gen[~net.gen["in_service"]].copy()
    gen_df["element_type"] = "gen"

    combined_df = pd.concat([bus_df, line_df, load_df, gen_df], ignore_index=True)

    def _by_level(counts):
        """Compact ' (400 kV: 10, 110 kV: 5)' breakdown, high voltage first."""
        if counts.empty:
            return ""
        parts = ", ".join(
            f"{int(level)} kV: {cnt}"
            for level, cnt in counts.sort_index(ascending=False).items()
        )
        return f"  ({parts})"

    gens_on_dc_buses = net.gen[net.gen["bus"].isin(disconnected_buses.index)]
    gen_names = (
        ", ".join(gens_on_dc_buses["name"].astype(str))
        if len(gens_on_dc_buses)
        else "none"
    )

    print("Disconnected elements:")
    print(f"  Buses : {len(disconnected_buses):3d}{_by_level(disconnected_buses['vn_kv'].value_counts())}")
    print(f"  Lines : {len(disconnected_lines):3d}{_by_level(disconnected_lines['voltage'].value_counts())}")
    print(f"  Loads : {len(disconnected_loads):3d}")
    print(f"  Gens  : {len(disconnected_gens):3d}")
    print(f"  Generators on disconnected buses: {gen_names}")

    # change to False to avoid saving a list of the disconnected elements to Excel
    save_disconnected_elements = True
    if save_disconnected_elements:
        combined_df.to_excel(
            "Disconnected_elements_from_DC_OPF_results.xlsx", index=False
        )


""" 3 Diagnostics of the disruption """


def disruption_diagnostics(net):

    load_pct = net.load.loc[~net.load["in_service"]].load_factor.sum() * 100
    gen_pct = net.gen[~net.gen["in_service"]].p_mw.sum() / net.gen.p_mw.sum() * 100
    bus_pct = len(net.bus[~net.bus["in_service"]]) / len(net.bus) * 100
    line_pct = len(net.line[~net.line["in_service"]]) / len(net.line) * 100

    print("Systemic impact (share of national total):")
    print(f"  Load not supplied : {load_pct:5.2f} %")
    print(f"  Generation lost   : {gen_pct:5.2f} %")
    print(f"  Buses out         : {bus_pct:5.2f} %")
    print(f"  Lines out         : {line_pct:5.2f} %")
