"""
Generate an Alkira opportunity brief for any company.

Usage:
    python generate_brief.py "Mary Kay"
    python generate_brief.py "Walmart" --output walmart_brief.md
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

import generate

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an Alkira opportunity brief for a target company."
    )
    parser.add_argument("company", help="Company name (e.g., 'Mary Kay')")
    parser.add_argument("--output", "-o", help="Output filename (e.g., brief.md)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show phase progress"
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key or not tavily_key:
        print("Error: ANTHROPIC_API_KEY and TAVILY_API_KEY must be set.")
        sys.exit(1)

    def status(phase: str) -> None:
        if args.verbose:
            print(f"  [{phase}]")

    start = time.time()
    brief = generate.generate_brief(api_key, tavily_key, args.company, status)
    print(f"\nCompleted in {time.time() - start:.0f} seconds.\n")
    print(brief)

    if args.output:
        with open(args.output, "w") as handle:
            handle.write(brief)
        print(f"\nBrief saved to: {args.output}")


if __name__ == "__main__":
    main()
