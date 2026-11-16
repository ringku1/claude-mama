import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print a greeting.")
    parser.add_argument("--name", default="world", help="who to greet")
    args = parser.parse_args(argv)
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
