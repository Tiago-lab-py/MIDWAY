from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class ApuracaoContexto:
    anomes: str
    total_consumidores: str | None
    base_dir: Path
    export_dir: Path
    marts_dir: Path
    processed_duckdb_path: Path
    raw_duckdb_path: Path
    data_arq: str
    timestamp_arq: str

    @classmethod
    def from_env(cls) -> "ApuracaoContexto":
        load_dotenv()

        anomes = os.getenv("ANOMES", "202605")
        base_dir = Path(os.getenv("MIDWAY_DATA_DIR", "data"))
        timestamp = datetime.now()

        return cls(
            anomes=anomes,
            total_consumidores=os.getenv("TOTAL_CONSUMIDORES"),
            base_dir=base_dir,
            export_dir=base_dir / "export",
            marts_dir=base_dir / "marts",
            processed_duckdb_path=base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb",
            raw_duckdb_path=base_dir / "raw" / f"iqs_adms_raw_{anomes}.duckdb",
            data_arq=timestamp.strftime("%Y%m%d"),
            timestamp_arq=timestamp.strftime("%Y%m%d%H%M%S"),
        )


CONTEXTO = ApuracaoContexto.from_env()
