"""Test script to verify connection to the Albion Online Data Project NATS stream."""

import asyncio
import nats
from nats.errors import TimeoutError
import sys
import os

# Force UTF-8 output on Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Status icons using ASCII for maximum console compatibility
OK = "[OK]"
ERR = "[ERR]"
WARN = "[!!]"
MSG = "[MSG]"
TIMEOUT = "[TO]"

NATS_SERVER = "nats://www.albion-online-data.com:4222"
NATS_USER = "public"
NATS_PASS = "thenewalbiondata"
PRIMARY_TOPIC = "marketorders.deduped.bulk"
FALLBACK_TOPICS = ["marketorders.v2", "marketorders.v3"]


async def main():
    print(f"Connecting to NATS server: {NATS_SERVER}")

    try:
        nc = await nats.connect(
            servers=[NATS_SERVER],
            user=NATS_USER,
            password=NATS_PASS,
            connect_timeout=10,
        )
        print(f"{OK} Successfully connected to NATS server!")
        print(f"   Server: {nc.connected_url}")
        print(f"   Stats: {nc.stats}")
        print()

        topics_to_try = [PRIMARY_TOPIC] + FALLBACK_TOPICS

        for topic in topics_to_try:
            print(f"Subscribing to topic: {topic}")
            try:
                sub = await nc.subscribe(topic)
                print(f"{OK} Subscribed to '{topic}'!")
                print()
                print(
                    "Waiting for messages (will stop after 3 messages or 30s timeout)..."
                )
                print("-" * 60)

                msg_count = 0
                max_messages = 3
                timeout_seconds = 30

                while msg_count < max_messages:
                    try:
                        msg = await sub.next_msg(timeout=timeout_seconds)
                        msg_count += 1
                        data = msg.data.decode("utf-8")
                        preview = data[:300] + "..." if len(data) > 300 else data
                        print(
                            f"\n{MSG} Message #{msg_count} (length: {len(data)} bytes):"
                        )
                        print(f"  Subject: {msg.subject}")
                        print(f"  Preview: {preview}")
                        print("-" * 60)
                    except TimeoutError:
                        print(f"{TIMEOUT} No messages received in {timeout_seconds}s.")
                        break

                if msg_count > 0:
                    print(f"\n{'=' * 60}")
                    print(
                        f"{OK} SUCCESS: Received {msg_count} message(s) from '{topic}'."
                    )
                    print("   NATS stream is WORKING!")
                    print(f"{'=' * 60}")
                    await nc.close()
                    return
                else:
                    print(f"{WARN} No messages on '{topic}', trying next topic...")

            except Exception as e:
                print(f"{ERR} Failed on topic '{topic}': {e}")
                continue

        print("\n" + ERR + " All topics exhausted. No messages received.")

        await nc.close()

    except Exception as e:
        print(f"{ERR} Connection Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
