#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.authorization_reconstruction import finalize_authorization_reviews


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schemas", type=Path, default=Path("schemas"))
    args = parser.parse_args()
    result = finalize_authorization_reviews(args.pack, args.output, args.schemas)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
