# Hardware documentation index

Updated: **2026-10-07**

This folder is the canonical index for manuals/datasheets used by the project. `hardware_sources.json` contains machine-readable source URLs and `download_hardware_docs.py` downloads the public PDFs into this directory on a machine with normal Internet access.

> **Repository-build note:** the artifact environment used for the 2026-10-07 audit could browse and verify the manufacturer pages, but its direct file-download path was unavailable. To avoid creating incomplete/corrupt PDFs, the cleaned repository contains the verified source manifest and downloader rather than fake PDF placeholders. Run `python docs/hardware/download_hardware_docs.py` from the repo root to populate the PDFs locally.

## Instrument manuals

| Hardware | Local filename | Source / relevance |
|---|---|---|
| Leybold GRAPHIX | `leybold_graphix_instruction_manual.pdf` | Current Leybold GRAPHIX ONE/TWO/THREE English instruction manual; RS-232/485 protocol and connector. |
| Granville-Phillips / MKS 475 | `mks_series_475_convectron_manual.pdf` | Series 475 instruction manual, Rev J (March 2020); analog output and option/interface definitions. |
| MKS PDR-D-1 / D-2 | `mks_pdr_d1_d2_manual.pdf` | Legacy PDR-D manual. Source is an archival mirror because a current MKS-hosted copy was not found. |
| LAUDA PRO / RP 290 E | `lauda_pro_base_operation_manual.pdf` | PRO with Base remote operating instructions; Ethernet process-interface commands. |
| LAUDA RP 290 E | `lauda_rp290e_datasheet.pdf` | Product data for the RP 290 E family/configuration; verify exact unit/options on the physical nameplate. |
| Agilent 7890A | `agilent_7890a_operating_guide.pdf` | 7890A GC operating guide. |
| Agilent 7890A | `agilent_7890a_user_manual_collection.pdf` | Agilent manual collection/index for the 7890A. |
| Agilent 7890A | `agilent_7890a_advanced_user_guide.pdf` | Advanced user guide; archival mirror is used in the manifest if Agilent no longer serves this exact legacy PDF directly. |

## Embedded/control hardware

| Hardware | Local filename | Source / relevance |
|---|---|---|
| Arduino Due | `arduino_due_datasheet.pdf` | Board datasheet, power-input and 3.3 V I/O constraints. |
| Feather RP2040 Adalogger | `adafruit_feather_rp2040_adalogger_guide.pdf` | Pinout, A0–A3 ADC inputs, USB-C, microSD and board usage. |
| RP2040 MCU | `rp2040_datasheet.pdf` | MCU ADC/electrical characteristics. |
| MCP9600/MCP9601 | `microchip_mcp960x_datasheet.pdf` | Thermocouple interface used by `firmware/thermocouple_reader`. |
| Mean Well HDR-150 | `meanwell_hdr150_datasheet.pdf` | Main DIN-rail 24 V supply family. |
| Mean Well DDR-15 | `meanwell_ddr15_datasheet.pdf` | 24→12 V and 24→5 V isolated DIN DC/DC converters. |
| SMC VQC1000/2000 | `smc_vqc1000_2000_operation_manual.pdf` | Valve/manifold handling and electrical information. |

## Hardware that still needs exact model documentation

The following should **not** be treated as fully pinned down until the physical part number is recorded:

- the exact Elegoo 4-channel relay-board revision/schematic;
- the exact MKS Baratron model/range attached to the PDR-D-1;
- the exact LAUDA RP 290 E option/package represented by serial `S230000611` (the family manuals are applicable, but installed options should be checked on the unit);
- Phoenix Contact distribution blocks selected in the final live procurement BOM.

## Keeping this directory current

1. Prefer manufacturer-hosted PDFs.
2. Do not overwrite a manual with a similarly named manual for a newer product generation.
3. Record legacy/archive sources explicitly.
4. When an exact physical model/revision changes, update `hardware_sources.json` and this README.
5. Keep procurement pages/BOM links separate from manuals unless the page is the only authoritative source for a part.
