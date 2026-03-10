# Copyright 2024 Drone New Method Project
# SPDX-License-Identifier: Apache-2.0

"""SlotKPI dataclass and CSV writer (Section 7 of CONTEXT.md)."""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class SlotKPI:
    slot_id: str
    aisle_id: str
    attempt_count: int
    success: bool
    scan_quality: float
    time_spent_sec: float
    barcode_value: str = ""
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: Literal["SUCCESS", "PARTIAL", "MANUAL_REVIEW"] = "SUCCESS"


_FIELDS = [f.name for f in SlotKPI.__dataclass_fields__.values()]


class SlotKPIWriter:
    """Append-only CSV writer.  Flushes after every row for crash safety."""

    def __init__(self, output_dir: str = "/tmp/Drone_new_method/kpi") -> None:
        os.makedirs(output_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._filepath = os.path.join(output_dir, f"slot_kpi_{stamp}.csv")
        self._file = open(self._filepath, "w", newline="")  # noqa: SIM115
        self._writer = csv.DictWriter(self._file, fieldnames=_FIELDS)
        self._writer.writeheader()
        self._file.flush()

    # -- public API ----------------------------------------------------------

    @property
    def filepath(self) -> str:
        return self._filepath

    def write(self, kpi: SlotKPI) -> None:
        self._writer.writerow(asdict(kpi))
        self._file.flush()

    def close(self) -> None:
        self._file.close()
