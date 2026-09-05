import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from agents.coordinator import run_pipeline

topic = sys.argv[1] if len(sys.argv) > 1 else "the current state of AI agent frameworks"


async def main():
    result = await run_pipeline(topic)
    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2))


asyncio.run(main())
