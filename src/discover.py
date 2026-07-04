"""
Device discovery placeholder.

The Sony ES / ZA-series control protocol does not support SSDP discovery;
receivers are configured manually by IP address (use a DHCP reservation).

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""


async def sony_avrs() -> list:
    """Return an empty list: discovery is not supported."""
    return []
