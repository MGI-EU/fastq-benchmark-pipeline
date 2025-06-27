import os
import sys
from collections import defaultdict


def usage():
    print(f"Usage:\npython {sys.argv[0]} mates1.fastq [mates2.fastq]")


def find_common_readlen(filename: str):
    freqs = defaultdict(int)

    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if i % 4 == 1:  # sequence lines are at index 1, 5, 9, etc.
                freqs[len(line) - 1] += 1  # -1 to account for '\n'

    max_freq = 0
    common_len = 0
    for length, freq in freqs.items():
        if freq > max_freq:
            max_freq = freq
            common_len = length

    return common_len


def out_path(filename, mcl: int):
    # Remove suffixes
    basename = os.path.basename(filename)
    out = basename.replace(".fq", "").replace(".fastq", "")
    out = f"{out}_len-{mcl}.fastq"
    print(f"Writing reads to {out}...", file=sys.stderr)
    return out


def process_reads_se(mates1: str, mcl: int):
    out1 = out_path(mates1, mcl)
    mcl += 1  # to account for '\n'

    with open(mates1, "r") as fin, open(out1, "w") as fout:
        lines = []
        for i, line in enumerate(fin):
            lines.append(line)
            if (i + 1) % 4 == 0:
                if len(lines[1]) == mcl:
                    fout.write("".join(lines))
                lines.clear()


def process_reads_pe(mates1: str, mates2: str, mcl: int):
    out1 = out_path(mates1, mcl)
    out2 = out_path(mates2, mcl)

    mcl += 1  # to account for '\n'

    with (
        open(mates1, "r") as fin1,
        open(mates2, "r") as fin2,
        open(out1, "w") as fout1,
        open(out2, "w") as fout2,
    ):
        lines1 = []
        lines2 = []
        for (i1, line1), (i2, line2) in zip(enumerate(fin1), enumerate(fin2)):
            lines1.append(line1)
            lines2.append(line2)

            if (i1 + 1) % 4 == 0:
                if len(lines1[1]) == len(lines2[1]) == mcl:
                    fout1.write("".join(lines1))
                    fout2.write("".join(lines2))

                lines1.clear()
                lines2.clear()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    mates1 = sys.argv[1]
    mcl = find_common_readlen(mates1)

    print(f"Most common length is: {mcl}", file=sys.stderr)

    if len(sys.argv) == 3:
        mates2 = sys.argv[2]
        process_reads_pe(mates1, mates2, mcl)
    else:
        process_reads_se(mates1, mcl)
