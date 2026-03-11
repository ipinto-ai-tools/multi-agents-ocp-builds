import argparse
from agents.graph import orchestrate

parser = argparse.ArgumentParser()

parser.add_argument("--title")
parser.add_argument("--description")

args = parser.parse_args()

result = orchestrate(args.title, args.description)

print("\n--- RESULT ---")

for k, v in result.items():
    print(f"\n{k.upper()}")
    print(v)
