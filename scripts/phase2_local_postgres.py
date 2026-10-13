"""Explicit dedicated Amidst PostgreSQL lifecycle; no autostart/global services."""

import argparse
import json

from amidst.local_storage.bootstrap import SETTINGS_PATH, start, stop
from amidst.local_storage.postgres import PostgresProductStore, PostgresSettings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    args = parser.parse_args()
    if args.action == "stop":
        stop()
        print(json.dumps({"status": "STOPPED", "local_only": True, "autostart": False}))
        return
    settings = start() if args.action == "start" else PostgresSettings.load(SETTINGS_PATH)
    with PostgresProductStore(settings) as store:
        print(json.dumps(store.context(), sort_keys=True))


if __name__ == "__main__":
    main()
