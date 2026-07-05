#!/usr/bin/env python3
"""Quick test of the web API endpoint."""

import asyncio
import aiohttp
import json
import sys

async def test_web_api(host: str):
    """Test connection to the receiver's web API."""

    print(f"Testing web API on {host}...\n")

    # Test 1: Simple GET
    print("1. Trying GET /request.cgi")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{host}/request.cgi", timeout=aiohttp.ClientTimeout(total=5)) as r:
                print(f"   Status: {r.status}")
                print(f"   Response: {await r.text()}\n")
    except Exception as e:
        print(f"   ✗ Failed: {e}\n")

    # Test 2: POST with audio.puredirect query
    print("2. Trying POST to query audio.puredirect")
    payload = {
        "type": "http_get",
        "packet": [{"id": 1, "feature": "audio.puredirect"}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{host}/request.cgi",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                print(f"   Status: {r.status}")
                data = await r.json(content_type=None)
                print(f"   Response: {json.dumps(data, indent=2)}\n")
    except Exception as e:
        print(f"   ✗ Failed: {e}\n")

    # Test 3: Try different ports
    print("3. Trying different ports...")
    for port in [8080, 8888, 9000, 80]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{host}:{port}/request.cgi",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as r:
                    print(f"   ✓ Port {port} is open (status {r.status})")
        except Exception as e:
            pass  # silent fail

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.100"
    asyncio.run(test_web_api(host))
