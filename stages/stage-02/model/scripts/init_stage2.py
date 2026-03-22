from pathlib import Path


def main() -> None:
    dirs = [
        "data/raw/uk-dale",
        "data/processed",
        "artifacts/models",
        "runs",
        "logs",
    ]

    for d in dirs:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        print(f"Created: {p}")


if __name__ == "__main__":
    main()
