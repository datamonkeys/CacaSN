#!/usr/bin/env python3
"""Lançador: o mesmo que `python -m caca_sn`. Mantido para agendamentos existentes."""

import sys

from caca_sn.cli import main

if __name__ == "__main__":
    sys.exit(main())
