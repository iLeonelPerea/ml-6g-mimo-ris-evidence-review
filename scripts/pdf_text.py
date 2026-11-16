#!/usr/bin/env python3
"""Prints the text of a PDF page by page, under lines '=== page N of M ==='."""
import argparse
import re
import subprocess


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=0, help="last page (default: the last page of the file)")
    args = parser.parse_args(argv)
    info = subprocess.run(["pdfinfo", args.pdf], capture_output=True, text=True, check=True).stdout
    total = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    last = min(args.last or total, total)
    text = subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(args.first), "-l", str(last), args.pdf, "-"],
                          capture_output=True, text=True, check=True).stdout
    for n, page in zip(range(args.first, last + 1), text.split("\f")):
        print(f"=== page {n} of {total} ===")
        print(page.strip())


if __name__ == "__main__":
    main()
