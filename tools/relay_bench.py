"""Talk to the relay controller by hand, without the dashboard.

    python tools/relay_bench.py COM14

Close the dashboard first: only one program can open the COM port at a time.
Commands at the prompt:  5,1  (relay 5 on)   5,0  (relay 5 off)   status   off   q
"""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
runpy.run_module("pneumatic_valve_panel.serial.pneumatic_communicator", run_name="__main__")
