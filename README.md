# MIRACA

[MIRACA](https://miraca-project.eu) (Multi-hazard Infrastructure Risk Assessment
for Climate Adaptation) is a research project building an evidence-based decision
support toolkit that meets real world demands.

This project has received funding from the European Union’s Horizon Europe research
programme under grant agreement No 101004174.

---

## Use Case 5 — Flooding and Landslides in Slovenia

### Objective

UC5 focuses on analyzing the impact of landslides and climate change-driven flooding
on the reliability of Slovenia's power and gas networks. Slovenia faces increasingly
frequent extreme weather events, such as droughts and floods, due to climate change,
which poses significant risks to its energy systems.

### What the notebook does

[`book/Use_Case_5_v1.ipynb`](book/Use_Case_5_v1.ipynb) evaluates the vulnerability of
Slovenia's electricity transmission system to single and compound natural hazards,
using a full [pandapower](https://www.pandapower.org/) model of the national grid
(191 buses, 282 lines, 91 generators, 212 loads). Hazard footprints follow historical
events, with intensities deliberately amplified to represent plausible future
conditions under a changing climate. It runs three analyses:

1. **Flooding** — major historical Sava River floods in the upper (Radovljica, 1926),
   middle (Litija, 2023) and lower (Čatež ob Savi, 2010) corridors. A scenario is
   selected (`upper` / `middle` / `lower`, or `all` for a three-region worst case);
   substations within a 5 km hazard zone are taken out of service.
2. **Landslide** — a chosen substation (e.g. `BOHINJ`) is disabled as a single point
   of failure.
3. **Compound hazard** — a flood and a landslide combined.

Each grid state is solved with a **DC optimal power flow (DC OPF)** and mapped (bus
voltage and line loading, disconnected elements in black). For every scenario the
notebook reports generation cost, maximum line loading, indirect losses, energy not
supplied, and the share of buses, lines, load and generation disconnected — tracing
impacts from network outages to asset-level line overloads to systemic generation and
demand loss.

### Repository structure

```
book/
  Use_Case_5_v1.ipynb    the main analysis notebook
src/                     simulation and plotting modules
inputs/
  pickle_files/          pandapower network and load profiles
  geodata_files/         river, region and country-boundary geometries
environment.yaml         conda environment specification
```

### Getting started

1. Create and activate the environment:
   ```bash
   conda env create -f environment.yaml
   conda activate miraca
   ```
2. Open `book/Use_Case_5_v1.ipynb` with the **miraca** kernel and run the cells top to
   bottom. Use the marked cells to choose the flooding scenario and landslide
   substation.

Running the notebook (re)generates the git-ignored `DC_OPF_results_*.xlsx` files.
