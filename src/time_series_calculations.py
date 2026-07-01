# -*- coding: utf-8 -*-
"""
# Project: MIRACA
# License: MIT License
# Copyright (c) 2024 miracaEU Contributors
# See LICENSE file for details.
"""

import os
import pandas as pd
import geopandas as gpd
import pandapower as pp
from pandapower.topology import unsupplied_buses

"""
    Time Series and Repeated Calculations
"""

# Get the current working directory
current_folder = os.getcwd()


def assign_slack(net):
    # Dynamically assign the slack bus to the generator with the highest max_p_mw
    biggest_unit_idx = net.gen[
        "p_mw"
    ].idxmax()  # Get the index of the generator with the highest max_p_mw
    net.gen["slack"] = False  # Set all generators' slack status to False
    net.gen.loc[biggest_unit_idx, "slack"] = (
        True  # Assign slack bus to the biggest unit
    )


def restore_original_net(net, net_bus_copy, net_line_copy):
    # Restore original buses and lines (in_service data)
    net.bus = net_bus_copy.copy()
    net.line = net_line_copy.copy()
    # Reset network results
    pp.reset_results(net)
    # Restore original min and max. values
    net.gen["min_p_mw"] = net.gen["original_min_p_mw"]
    net.gen["max_p_mw"] = net.gen["original_max_p_mw"]
    net.gen["in_service"] = True
    net.gen["controllable"] = True
    net.gen["slack"] = False
    # Assign slack
    assign_slack(net)
    # Set loads in service
    net.load["in_service"] = True
    # Reset the gen tracking
    initialize_gen_tracking(net)


# Step 1: Use Time-Series Data to Dynamically Update Loads
def update_loads(network, time_series, time_step):
    """
    Update the active power of loads in the pandapower network for the given time step.

    Parameters:
    - network: pandapowerNet, the pandapower network model
    - time_series: pd.DataFrame, country-level time-series electricity demand
    - time_step: int or datetime, the current time step index or timestamp

    Returns:
    - None: Updates the network in place
    """
    # Find columns that start with the expected prefix
    matching_columns = [
        col for col in time_series.columns if col.startswith("SI_load_actual")
    ]
    # Proceed if at least one matching column exists
    if matching_columns:
        # Get the load for the country
        country_load = time_series.loc[
            time_step, matching_columns[0]
        ]  # Use the first matching column
        network.load["p_mw"] = network.load["load_factor"] * country_load


"""
ECB Exchange Rate 
https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html
"""

ex_rate = 1.0614  # Average EUR VS USD ECB Exchange Rate for January 2017

# Ramp_rate data and other costs in USD based on fueltypes (USD is later converted in EUR based on official ECB Exchange Rate)
ramp_data = {
    "Coal": {
        "ramp_rate": [0.6, 4.3, 8],
        "start_up_cost": [100, 175, 250],
        "shut_down_cost": [10, 17.5, 25],
        "start_time": [4, 6.5, 9],
        "shutdown_time": [2, 5.5, 9],
        "min_on_time": [0, 6, 12],
        "min_off_time": [0, 6, 12],
    },
    "Natural Gas": {
        "ramp_rate": [0.8, 15.4, 30],
        "start_up_cost": [20, 85, 150],
        "shut_down_cost": [2, 8.5, 15],
        "start_time": [2, 3, 4],
        "shutdown_time": [1, 2.5, 4],
        "min_on_time": [0, 1, 2],
        "min_off_time": [0, 0.5, 1],
    },
    "Nuclear": {
        "ramp_rate": [0, 2.5, 5],
        "start_up_cost": [1000, 1000, 1000],
        "shut_down_cost": [1000, 1000, 1000],
        "start_time": [24, 24, 24],
        "shutdown_time": [24, 24, 24],
        "min_on_time": [24, 48, 72],
        "min_off_time": [24, 48, 72],
    },
    "Hydro": {
        "ramp_rate": [15, 20, 25],
        "start_up_cost": [0, 2.5, 5],
        "shut_down_cost": [0, 0.25, 0.5],
        "start_time": [0, 0.5, 1],
        "shutdown_time": [0, 0.5, 1],
        "min_on_time": [0, 0.5, 1],
        "min_off_time": [0, 0.5, 1],
    },
}


def update_gens(network, fuel_data=ramp_data, val=0):
    """
    Update the active power of generators with ramp constraints and economic costs.

    Parameters:
    - network: pandapowerNet, the pandapower network model
    - fuel_data: dict, mapping of fuel type to ramp rate and cost parameters
    - val: int, 0 = min value, 1 = avg value, 2 = max value
    Returns:
    - None: Updates the network in place
    """

    previous_p = network.res_gen["p_mw"]

    for gen_idx, row in network.gen.iterrows():
        fuel_type = row["fueltype"]
        rated_capacity = row["p_mw"]

        if fuel_type == "CCGT":
            fuel_type = "Natural Gas"
        elif fuel_type == "lignite":
            fuel_type = "Coal"
        elif fuel_type == "nuclear":
            fuel_type = "Nuclear"
        elif fuel_type == "hydro" or fuel_type == "ror" or fuel_type == "PHS":
            fuel_type = "Hydro"
        else:
            fuel_type = None

        if row.slack:
            continue  # Skip slack generator

        if fuel_type is not None:

            # Get ramp rate as %/min, convert to MW/hour
            ramp_rate_percent = fuel_data[fuel_type]["ramp_rate"][val]
            ramp_rate_mw_hr = rated_capacity * (ramp_rate_percent / 100) * 60

            # Set ramp-constrained bounds
            network.gen.at[gen_idx, "min_p_mw"] = max(
                previous_p[gen_idx] - ramp_rate_mw_hr, row.get("original_min_p_mw", 0)
            )
            network.gen.at[gen_idx, "max_p_mw"] = min(
                previous_p[gen_idx] + ramp_rate_mw_hr,
                row.get("original_max_p_mw", rated_capacity),
            )

            # Store economic values
            network.gen.at[gen_idx, "start_up_cost"] = (
                fuel_data[fuel_type]["start_up_cost"][val] * ex_rate
            )
            network.gen.at[gen_idx, "shut_down_cost"] = (
                fuel_data[fuel_type]["shut_down_cost"][val] * ex_rate
            )
            network.gen.at[gen_idx, "start_time_hr"] = fuel_data[fuel_type][
                "start_time"
            ][val]
            network.gen.at[gen_idx, "shutdown_time_hr"] = fuel_data[fuel_type][
                "shutdown_time"
            ][val]
            network.gen.at[gen_idx, "min_on_time_hr"] = fuel_data[fuel_type][
                "min_on_time"
            ][val]
            network.gen.at[gen_idx, "min_off_time_hr"] = fuel_data[fuel_type][
                "min_off_time"
            ][val]


def initialize_gen_tracking(network):
    """
    Adds tracking columns to network.gen for operational logic.
    """
    cols = {
        "status": "on",  # 'off', 'starting', 'on', 'stopping'
        "time_running_hr": 0.0,
        "time_idle_hr": 0.0,
        "start_up_progress_hr": 0.0,
        "shut_down_progress_hr": 0.0,
        "operation_can_start": True,
        "operation_can_stop": True,
        "start_up_triggered": False,
        "shut_down_triggered": False,
        "operating_cost_this_step": 0.0,
    }
    for col, default in cols.items():
        # if col not in network.gen.columns:
        network.gen[col] = default


def update_gen_operation_logic(network, dt_hours=1.0):
    """
    Updates generator timers and operational flags based on current status.
    """
    for gen_idx, row in network.gen.iterrows():
        status = row["status"]

        # Get constraints
        min_on = row.get("min_on_time_hr_selected", 0.0) or 0.0
        min_off = row.get("min_off_time_hr_selected", 0.0) or 0.0
        start_up_time = row.get("start_up_time_hr_selected", 0.0) or 0.0
        shut_down_time = row.get("shut_down_time_hr_selected", 0.0) or 0.0

        # Update timers and transitions
        if status == "on":
            network.gen.at[gen_idx, "time_running_hr"] += dt_hours
            network.gen.at[gen_idx, "time_idle_hr"] = 0.0
            network.gen.at[gen_idx, "start_up_progress_hr"] = 0.0
            network.gen.at[gen_idx, "shut_down_progress_hr"] = 0.0

        elif status == "off":
            network.gen.at[gen_idx, "time_idle_hr"] += dt_hours
            network.gen.at[gen_idx, "time_running_hr"] = 0.0
            network.gen.at[gen_idx, "start_up_progress_hr"] = 0.0
            network.gen.at[gen_idx, "shut_down_progress_hr"] = 0.0

        elif status == "starting":
            progress = row["start_up_progress_hr"] + dt_hours
            network.gen.at[gen_idx, "start_up_progress_hr"] = progress
            if progress >= start_up_time:
                network.gen.at[gen_idx, "status"] = "on"
                network.gen.at[gen_idx, "start_up_triggered"] = True
                network.gen.at[gen_idx, "time_running_hr"] = 0.0

        elif status == "stopping":
            progress = row["shut_down_progress_hr"] + dt_hours
            network.gen.at[gen_idx, "shut_down_progress_hr"] = progress
            if progress >= shut_down_time:
                network.gen.at[gen_idx, "status"] = "off"
                network.gen.at[gen_idx, "shut_down_triggered"] = True
                network.gen.at[gen_idx, "time_idle_hr"] = 0.0

        # Determine if start/stop is allowed
        can_start = row["time_idle_hr"] >= min_off and status == "off"
        can_stop = row["time_running_hr"] >= min_on and status == "on"

        network.gen.at[gen_idx, "operation_can_start"] = can_start
        network.gen.at[gen_idx, "operation_can_stop"] = can_stop


def calculate_gen_costs(network, dt_hours=1.0, operating_costs=None):
    """
    Calculates operating costs per time step.
    """

    for gen_idx, row in network.gen.iterrows():
        status = row["status"]
        power = network.res_gen["p_mw"][gen_idx]
        cost = 0.0

        # Operating cost only when fully on
        if status == "on":
            # Avoid negative costs
            if power < 0:
                cost += 0
            else:
                cost += row.cost_per_mw * power * dt_hours

        # Start-up cost (once)
        if row.get("start_up_triggered", False):
            cost += row.get("start_up_cost_selected", 0.0) * power

        # Shut-down cost (once)
        if row.get("shut_down_triggered", False):
            cost += row.get("shut_down_cost_selected", 0.0) * power

        network.gen.at[gen_idx, "operating_cost_this_step"] = cost


def apply_status_to_opf_constraints(network):
    """
    Updates pandapower generator constraints based on operational status.
    """
    for gen_idx, row in network.gen.iterrows():
        status = row["status"]

        if status == "on":
            network.gen.at[gen_idx, "controllable"] = True
            # Keep min/max as defined
        else:
            network.gen.at[gen_idx, "controllable"] = False


def update_storage(network):
    """
    Automatically update the SOC in net.storage after each iteration

        - negative results  =  charging storage
        - positive results  =  discharging from storage

    """

    # Resulting power_mw
    previous_p = network.res_storage["p_mw"]  # per h

    for idx, row in network.storage.iterrows():
        # Calculate new SOC based on resulting output
        previous_SOC = row["soc_percent"]
        network.storage.at[idx, "soc_percent"] = previous_SOC - (
            previous_p[idx] * 100 / row["max_e_mwh"]
        )


def enforce_storage_energy_limits(network, dt_hours=1.0):
    for idx, row in network.storage.iterrows():
        soc = row["soc_percent"]
        max_e = row["max_e_mwh"]
        # min_e = row.get("min_e_mwh", 0.0)
        # eff = row["efficiency_percent"] / 100.0
        max_p_original = row["original_max_p_mw"]
        min_p_original = row["original_min_p_mw"]

        # Current energy in MWh
        e_now = soc / 100.0 * max_e

        # Max discharge allowed this step
        max_discharge_mw = 0 if e_now <= 0 else min(max_p_original, e_now)

        # Max charge allowed this step
        max_charge_mw = 0 if max_e == e_now else min(-min_p_original, max_e - e_now)
        max_charge_mw = -max_charge_mw

        if soc <= 80:
            # Set bounds
            network.storage.at[idx, "min_p_mw"] = max_charge_mw
        else:
            network.storage.at[idx, "min_p_mw"] = 0

        if soc >= 20:
            network.storage.at[idx, "max_p_mw"] = max_discharge_mw
        else:
            network.storage.at[idx, "max_p_mw"] = 0


""" Time dependant outages based on overloaded lines """


def check_overloads(net):
    # Initialize a list to store overloaded line indices
    overloaded_line_indices = []

    for idx, row in net.res_line.iterrows():
        if row.loading_percent > 100:
            net.line.at[idx, "in_service"] = False  # Mark line as out of service
            overloaded_line_indices.append(idx)  # Save index of overloaded line
            print(
                "Line at index",
                idx,
                "is overloaded and is thus disconnected from the grid.",
            )

    overloaded_lines = net.line.loc[overloaded_line_indices].copy()

    return overloaded_lines


""" Time series function with ramping, start-up/down-time processes and calculation of operating costs """


def check_unsupplied_buses(net, disconnected_buses):
    disconnected_buses_new = set(unsupplied_buses(net))
    new_affected = disconnected_buses_new - disconnected_buses
    disconnected_buses.update(disconnected_buses_new)
    affected_buses = list(new_affected)
    return affected_buses


""" Direct losses (equipment) """


def direct_economic_losses(net, affected_buses):
    avg_sub_cost = 9  # million € (HV substation)

    direct_losses = len(affected_buses) * avg_sub_cost
    return direct_losses


""" Indirect losses (economic damage) - oportunity costs """


def indirect_economic_losses(net, outage_duration):
    GDP_loss = 0
    # Save affected_loads
    affected_loads = net.load.loc[~net.load["in_service"]]

    folder_path = f"{current_folder}//inputs//geodata_files//loads_lau.geojson"

    if os.path.exists(folder_path):
        loads_lau = gpd.read_file(folder_path)
    else:
        print("No data in current folder/geodata_files")

    if not affected_loads.empty:

        results = []

        for lau_id in affected_loads.name:  # assuming this is a list of LAU_IDs

            affected_pop = loads_lau["pop"][loads_lau.LAU_ID == lau_id].item()
            gdp = loads_lau["gdp"][loads_lau.LAU_ID == lau_id].item()

            if affected_pop is None or gdp is None:
                continue  # skip bad rows

            GDP_region_per_day = gdp / 365  # GDP per day
            GDP_region_per_h = GDP_region_per_day / 24  # GDP per hour
            GDP_loss = (
                affected_pop * GDP_region_per_h * outage_duration
            ) / 10e6  # In million €

            results.append({"LAU_ID": lau_id, "pop": affected_pop, "gdp": GDP_loss})

        # Convert to DataFrame if needed
        df_results = pd.DataFrame(results)

        GDP_loss = df_results.gdp.sum() if not df_results.gdp.empty else 0

    return GDP_loss


def time_series_calculations(time_series_short, net, type="AC PF"):
    # Initialize an empty list to collect results
    results_list = []
    # First initialization
    initialize_gen_tracking(net)
    disconnected_buses = unsupplied_buses(net)

    for time_step in time_series_short.index:
        # 1 Update loads in the network for the current time step
        update_loads(network=net, time_series=time_series_short, time_step=time_step)

        # 2 Enforce limits before calculation
        enforce_storage_energy_limits(net)

        # 3 Run power flow simulation
        if type == "AC PF":
            pp.runpp(net)
        elif type == "DC PF":
            pp.rundcpp(net)
        elif type == "DC OPF":
            pp.rundcopp(net)
        elif type == "AC OPF":
            pp.runopp(net)

        # 4 Update ramping and bounds
        update_gens(network=net)

        # 5 Update operational logic
        update_gen_operation_logic(network=net, dt_hours=1.0)

        # 6 Apply status to OPF constraints
        apply_status_to_opf_constraints(net)

        # 7 Calculate costs
        calculate_gen_costs(network=net, dt_hours=1.0)

        # 8 Update storage SOC values
        update_storage(net)

        # 9 Check overloads - disruption event
        overloaded_lines = check_overloads(net)

        # 10 Check affected buses - disruption event
        affected_buses = check_unsupplied_buses(net, disconnected_buses)

        # 11 Calculate economic losses
        direct_losses = direct_economic_losses(net, affected_buses)
        indirect_losses = indirect_economic_losses(net, outage_duration=1.0)
        if indirect_losses is None:
            indirect_losses = 0

        # Collect key results
        results_list.append(
            {
                "time_step": time_step,
                "total_load_ref (MW)": net.load["p_mw"].sum(),
                "total_load_res (MW)": net.res_load["p_mw"].sum(),
                "total_gen_capacity (MW)": net.gen[net.gen.in_service]["p_mw"].sum(),
                "total_generation_res (MW)": net.res_gen["p_mw"].sum(),
                "total_gen_costs (€)": net.gen["operating_cost_this_step"].sum(),
                "max_line_loading (%)": net.res_line["loading_percent"].max(),
                "overloaded_lines": len(overloaded_lines),
                "affected_buses": len(affected_buses),
                "total_storage_injections (MW)": -(
                    net.res_storage["p_mw"].sum()
                ),  # Positive value for injecting to the grid (original value is negative)
                "direct_losses (million €)": direct_losses,
                "indirect_losses (million €)": indirect_losses,
            }
        )

        # Reset event flags
        net.gen["start_up_triggered"] = False
        net.gen["shut_down_triggered"] = False

    # Convert list to DataFrame at the end
    pf_results = pd.DataFrame(results_list)

    return pf_results
