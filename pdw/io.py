"""Chunked Parquet storage for simulated sequences (fix E1).

One row per sequence: scalar summary columns plus per-step list columns. Every
sequence stores indicators and flags, so all methods and thresholds can be evaluated
offline. Full state traces are stored separately (npz) for a few seeds only.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pdw.indicators import NAMES

SCALARS = ("scenario", "n", "m", "seed", "T", "end_reason", "tightness", "exceeds_need",
           "runtime", "safety_time", "safety_calls", "detect_time", "detect_calls", "lookahead_time")
ARRAYS = {  # column -> dtype
    "indicators": np.float32,   # flattened (T, 5)
    "unsafe": np.bool_,
    "deadlocked": np.bool_,
    "n_waiting": np.int16,
    "req_units": np.int32,
    "in_spike": np.bool_,
    "lookahead": np.float32,    # null when not computed
}


def results_to_table(results) -> pa.Table:
    cols = {k: [getattr(r, k) for r in results] for k in SCALARS}
    for k, dt in ARRAYS.items():
        vals = []
        for r in results:
            v = getattr(r, k)
            vals.append(None if v is None else np.asarray(v, dtype=dt).ravel())
        cols[k] = pa.array(vals, type=pa.list_(pa.from_numpy_dtype(dt)))
    return pa.table(cols)


def write_chunk(results, path: str) -> None:
    tmp = path + ".tmp"
    pq.write_table(results_to_table(results), tmp, compression="zstd")
    os.replace(tmp, path)  # atomic: a crashed chunk never looks complete (G3)


def chunk_files(run_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(run_dir, "chunks", "*.parquet")))


def _unpack(table: pa.Table) -> list[dict]:
    rows = []
    cols = {c: table.column(c).combine_chunks() for c in table.column_names}
    n = table.num_rows
    scal = {k: cols[k].to_pylist() for k in SCALARS if k in cols}
    arr = {}
    for k, dt in ARRAYS.items():
        if k not in cols:
            continue
        la = cols[k]
        offs = la.offsets.to_numpy()
        vals = la.values.to_numpy(zero_copy_only=False).astype(dt, copy=False)
        valid = la.is_valid().to_numpy(zero_copy_only=False)
        arr[k] = (offs, vals, valid)
    for i in range(n):
        row = {k: v[i] for k, v in scal.items()}
        for k, (offs, vals, valid) in arr.items():
            row[k] = vals[offs[i]:offs[i + 1]] if valid[i] else None
        if row.get("indicators") is not None:
            row["indicators"] = row["indicators"].reshape(-1, len(NAMES))
        rows.append(row)
    return rows


def read_chunk(path: str, columns=None) -> list[dict]:
    return _unpack(pq.read_table(path, columns=columns))


def read_summary(run_dir: str):
    import pandas as pd

    return pd.concat([pq.read_table(f, columns=list(SCALARS)).to_pandas() for f in chunk_files(run_dir)],
                     ignore_index=True)
