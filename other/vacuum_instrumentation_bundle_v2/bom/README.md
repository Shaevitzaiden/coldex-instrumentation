# BOM snapshots

This directory contains several BOM/checklist exports created at different stages of the hardware design. They are retained as historical snapshots rather than silently deleting purchasing work.

## Important

There is **not currently a single unambiguous canonical BOM filename** in this directory. In particular:

- `BOM_v2_9-18-2026.*` is a dated system BOM snapshot.
- `BOM_switch_panel_test_9-27-2026.*` is newer by date but appears to be a switch-panel-specific/test variant.
- `system_bom_checklist.*` tracks system completeness/status rather than being only a purchase order.
- older `BOM.xlsx`, `BOM_v1.*`, and `BOM (version 1).xlsx` are retained for traceability.

Before placing an order, reconcile the live working BOM against `docs/PROJECT_STATUS.md`. The later 24 V Phoenix Contact distribution-block discussion occurred after some of these snapshots, so do not assume the newest timestamp contains every subsequently discussed part.

Once the procurement design is frozen, rename/copy the authoritative sheet to something explicit such as `BOM_CURRENT.xlsx` and archive the others under a dated `archive/` folder.
