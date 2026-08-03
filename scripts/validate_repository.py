#!/usr/bin/env python3
"""Validează consistența repository-ului și a exporturilor publice."""

from scripts.afdj_core import project_root, validate_repository


if __name__ == "__main__":
    print(validate_repository(project_root()))
