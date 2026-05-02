from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


STAGE02_ROOT = Path(__file__).resolve().parents[1]
if str(STAGE02_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE02_ROOT))

from integration.registry_utils import (  # noqa: E402
    get_active_package_ref,
    load_registry,
    resolve_package_ref,
    save_registry,
)


def cmd_show() -> None:
    data = load_registry(STAGE02_ROOT)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_list() -> None:
    data = load_registry(STAGE02_ROOT)
    active = str(data.get("active_package", ""))
    packages = list(data.get("packages", []))
    for i, p in enumerate(packages, start=1):
        path = str(p.get("path", ""))
        mark = "*" if path == active else " "
        print(f"{mark} [{i}] id={p.get('id')} profile={p.get('profile')} status={p.get('status')}")
        print(f"    path={path}")


def cmd_set_active(package_id: str | None, package_path: str | None) -> None:
    if not package_id and not package_path:
        raise ValueError("Either --package-id or --package-path is required.")
    data = load_registry(STAGE02_ROOT)
    packages = list(data.get("packages", []))

    ref = ""
    if package_id:
        for p in packages:
            if str(p.get("id")) == package_id:
                ref = str(p.get("path", ""))
                break
        if not ref:
            raise ValueError(f"Unknown package-id: {package_id}")
    else:
        ref = str(package_path).strip()

    abs_path = resolve_package_ref(STAGE02_ROOT, ref)
    if not abs_path.exists():
        raise FileNotFoundError(f"Package file not found: {abs_path}")

    data["active_package"] = ref
    path = save_registry(STAGE02_ROOT, data)
    print(f"Active package updated: {ref}")
    print(f"Registry saved: {path}")


def cmd_verify_active() -> None:
    ref = get_active_package_ref(STAGE02_ROOT)
    abs_path = resolve_package_ref(STAGE02_ROOT, ref)
    print(f"active_package={ref}")
    print(f"resolved_path={abs_path}")
    print(f"exists={abs_path.exists()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Stage-02 package registry.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", help="Print full registry json.")
    sub.add_parser("list", help="List packages with active marker.")
    set_p = sub.add_parser("set-active", help="Set active package by id or path.")
    set_p.add_argument("--package-id", default="")
    set_p.add_argument("--package-path", default="")
    sub.add_parser("verify-active", help="Resolve active package and verify file exists.")

    args = parser.parse_args()
    if args.cmd == "show":
        cmd_show()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "set-active":
        cmd_set_active(
            package_id=args.package_id.strip() or None,
            package_path=args.package_path.strip() or None,
        )
    elif args.cmd == "verify-active":
        cmd_verify_active()


if __name__ == "__main__":
    main()
