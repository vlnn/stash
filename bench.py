import argparse
import os
import random
import statistics
import string
import subprocess
import sys
import tempfile
import time

SIZES = (1_000, 10_000, 50_000)
RUNS = 25
HERE = os.path.dirname(os.path.abspath(__file__))
STRESS_SYLLABLES = ["ka", "ro", "pre", "st", "an", "dev", "op", "ssh", "web", "prod", "stag", "ing", "ctx", "lo", "git"]


def realistic_vocabulary(rng, count):
    return ["".join(rng.choices(string.ascii_lowercase, k=rng.randint(3, 9))) for _ in range(count)]


def stress_vocabulary(rng, count):
    return ["".join(rng.choices(STRESS_SYLLABLES, k=rng.randint(1, 3))) for _ in range(count)]


def database_line(rng, vocabulary):
    keywords = " ".join(rng.sample(vocabulary, rng.randint(2, 5)))
    title = " ".join(rng.sample(vocabulary, rng.randint(2, 4))).capitalize()
    return f"{keywords} | {title} | echo {rng.randrange(10**9)}\n"


def write_database(directory, size, vocabulary, rng):
    db_dir = os.path.join(directory, f"db-{size}")
    os.makedirs(db_dir)
    with open(os.path.join(db_dir, "default.txt"), "w", encoding="utf-8") as file:
        file.writelines(database_line(rng, vocabulary) for _ in range(size))
    return db_dir


def queries_for(vocabulary):
    first, second, third = vocabulary[:3]
    return ("", "a", first[:3], f"{second} {first[:2]}", third[0] + third[-1], "zzzzq")


def milliseconds(argv, env):
    start = time.perf_counter()
    subprocess.run(argv, env=env, stdout=subprocess.DEVNULL, check=True, cwd=HERE)
    return (time.perf_counter() - start) * 1000


def summary(samples):
    ordered = sorted(samples)
    return f"p50 {statistics.median(ordered):6.1f} ms   p95 {ordered[int(len(ordered) * 0.95) - 1]:6.1f} ms"


def measure(argv, env):
    return summary([milliseconds(argv, env) for _ in range(RUNS)])


def bench_size(python, directory, size, stress):
    rng = random.Random(42)
    vocabulary = (stress_vocabulary if stress else realistic_vocabulary)(rng, 3_000)
    env = {**os.environ, "db_dir": write_database(directory, size, vocabulary, rng)}
    search = [python, "-S", "-X", "utf8", "run.py", "search"]
    for query in queries_for(vocabulary):
        print(f"{size:>6} entries  query {query!r:16} {measure([*search, query], env)}")


def main():
    parser = argparse.ArgumentParser(description="Per-keystroke latency of the Alfred script filter")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--stress", action="store_true", help="tiny vocabulary, most queries match most entries")
    args = parser.parse_args()
    print(f"{'python startup only':38} {measure([args.python, '-S', '-c', 'pass'], os.environ)}")
    with tempfile.TemporaryDirectory() as directory:
        for size in SIZES:
            bench_size(args.python, directory, size, args.stress)


if __name__ == "__main__":
    main()
