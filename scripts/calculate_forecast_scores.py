#!/usr/bin/env python3
"""Calculează scorurile prognozelor istorice."""

from scripts.afdj_core import calculate_scores, project_root


if __name__ == "__main__":
    rows = calculate_scores(project_root())
    print(f"Scoruri calculate: {len(rows)} combinații stație/orizont")
