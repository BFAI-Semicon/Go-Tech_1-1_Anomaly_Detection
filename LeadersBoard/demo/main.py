import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    _ = parser.parse_args()
    print("hello")
if __name__ == "__main__":
    main()
