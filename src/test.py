# pylint: skip-file
# flake8: noqa
"""Interactive test harness for the Sony ES (ZA) protocol client.

Usage: python3 src/test.py <receiver-ip>
"""
import asyncio
import logging
import sys

from za_protocol import SonyZaConnection, Zone, ZaEvents

_LOG = logging.getLogger(__name__)


async def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "<xx.xx.xx.xx>"
    conn = SonyZaConnection(host)

    def on_zone_update(zone, state):
        print(f"UPDATE {zone.name}: {state}")

    def on_sound_field(code):
        print(f"SOUND FIELD: 0x{code:02x}")

    conn.events.on(ZaEvents.ZONE_UPDATE, on_zone_update)
    conn.events.on(ZaEvents.SOUND_FIELD, on_sound_field)

    await conn.connect()
    print("connected, initial state queried; listening for events...")
    await asyncio.sleep(2)

    for zone in Zone:
        st = conn.zones[zone]
        print(f"{zone.name}: volume={st.volume} input=0x{st.input_code:02x}"
              if st.input_code is not None else f"{zone.name}: volume={st.volume}")

    # keep listening; change things on the receiver front panel / web UI
    # and watch the pushed notifications
    await asyncio.sleep(600)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
