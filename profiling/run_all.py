"""Run every profiling script in report order (Bảng 2.1 → 2.5).

Run: python profiling/run_all.py   (about 6–8 minutes on the full 2024–2025 data)
"""

import column_quality
import issues
import overview
import relationships
from common import Timer

if __name__ == "__main__":
    for module in (overview, column_quality, relationships, issues):
        with Timer(module.__name__):
            module.main()
