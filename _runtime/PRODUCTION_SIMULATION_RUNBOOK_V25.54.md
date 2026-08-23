# v25.54 Production Simulation Lab

## Native GUI
Open **LAN Pool** → **PRODUCTION SIMULATION LAB v25.54**.
- **SIM LAB**: runs the standard deterministic 8-seed profile.
- **REPLAY**: runs fixed seed 991 to verify reproducibility.

## CLI
```text
python HMS_Codex_ProductionSimulationLab.py --root . --seeds 11,23,37,41,59,73,89,101 --cycles 300 --output production-simulation.json
```

## Safety
The lab uses synthetic identities only. It does not read or mutate real OAuth/auth files, does not call a real Codex model, does not consume quota, and does not require a real SMB/NAS share.

`PASS_PRODUCTION_SIMULATION_LAB_V25_54` is never a production certificate.
