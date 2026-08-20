from ai_db_benchmark.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["benchmark", "--database", "sqlite", "--suite", "all"]))
