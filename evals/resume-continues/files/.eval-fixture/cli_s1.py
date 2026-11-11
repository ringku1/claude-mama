import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print a greeting.")
    parser.add_argument("--name", default="world", help="who to greet")
    parser.add_argument("--verbose", action="store_true", help="print debug output")
    args = parser.parse_args(argv)
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
