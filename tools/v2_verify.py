#!/usr/bin/env python3
"""Verify v2 seals and published runs. 0 PASS; 1 FAIL; 2 UNKNOWN/WEAK."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sealedbench.v2.verification import verify

if __name__=='__main__':
    raise SystemExit(verify(os.environ.get('SEALEDBENCH_BATCH','b2')))
