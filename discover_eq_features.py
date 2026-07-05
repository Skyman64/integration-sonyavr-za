#!/usr/bin/env python3
"""
Quick discovery script to find available EQ and audio features on your Sony ES receiver.

Usage:
    python3 discover_eq_features.py <receiver_ip>

Example:
    python3 discover_eq_features.py 192.168.1.100
"""

import asyncio
import json
import sys
from src.web_api import SonyWebApi

# Comprehensive list of potential EQ and audio feature names
# Adjust based on your receiver's capabilities
POTENTIAL_FEATURES = [
    # Basic tone controls
    "audio.bass",
    "audio.treble",
    "audio.center",

    # Subwoofer and surround
    "audio.subwoofer",
    "audio.subwooferlevel",
    "audio.lfe",
    "audio.lfefx",

    # Speaker levels
    "audio.frontspeakerlevel",
    "audio.centerspeakerlevel",
    "audio.surroundlevel",
    "audio.surroundrearspklevel",
    "audio.rearlevel",
    "audio.dlsurroundlevel",

    # Balance and pan
    "audio.balancelr",
    "audio.balance",
    "audio.pan",

    # Distance/delay
    "audio.speakerdistance",
    "audio.speakerdelay",
    "audio.distlevel",

    # Already known features
    "audio.puredirect",
    "audio.soundoptimizer",
    "audio.neuralx",
    "audio.drangecomp",
    "audio.dualmono",

    # Additional processing
    "audio.bandwidth",
    "audio.phasecontrol",
    "audio.dcacfilter",
    "audio.outputmode",

    # Input-specific settings
    "audio.noisefilter",
    "audio.surr2chmode",
    "audio.hdmioutput",

    # Zone 2/3 specific (might not exist but worth trying)
    "zone2.bass",
    "zone2.treble",
    "zone3.bass",
    "zone3.treble",

    # System settings
    "audio.levelstandardization",
    "audio.referencelevel",
]


async def discover_features(host: str) -> None:
    """Query receiver and report available EQ features."""
    api = SonyWebApi(host)

    print(f"\n🔍 Discovering EQ features on {host}...\n")
    print("=" * 70)

    # Test in batches (to avoid large responses)
    batch_size = 5  # Smaller batches for stability
    available = {}
    unavailable = []
    errors = []

    for i in range(0, len(POTENTIAL_FEATURES), batch_size):
        batch = POTENTIAL_FEATURES[i : i + batch_size]
        try:
            results = await api.get_features(batch)

            for feature, value in results.items():
                if value is not None:
                    available[feature] = value
                    print(f"✓ {feature:40} = {value}")
                else:
                    unavailable.append(feature)
        except Exception as ex:
            errors.append(f"Error querying {batch}: {ex}")
            print(f"✗ Error in batch: {ex}")

    print("\n" + "=" * 70)
    print(f"\n📊 Summary:")
    print(f"   Available features: {len(available)}")
    print(f"   Not found: {len(unavailable)}")
    if errors:
        print(f"   Errors: {len(errors)}")

    if available:
        print(f"\n💾 Available features (for ENHANCEMENT_PLAN.md):\n")
        print("```json")
        print(json.dumps(available, indent=2))
        print("```")

        print(f"\n🔧 For const.py, add to AUDIO_SETTINGS:")
        print("```python")
        for feature in available:
            print(f'    "{feature}": [???],  # TODO: discover allowed values')
        print("```")

    if unavailable and len(unavailable) <= 20:
        print(f"\n⚠️  Features not found (might be unsupported):")
        for f in unavailable:
            print(f"   - {f}")


async def main() -> None:
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 discover_eq_features.py <receiver_ip>")
        print("\nExample: python3 discover_eq_features.py 192.168.1.100")
        sys.exit(1)

    host = sys.argv[1]
    try:
        await discover_features(host)
    except Exception as ex:
        print(f"\n❌ Failed to connect to {host}: {ex}")
        print("\nMake sure:")
        print("  - Receiver is powered on")
        print("  - IP address is correct")
        print("  - Network is reachable (ping the receiver first)")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
