import argparse
import os
import subprocess
import sys


def download_fastq(cont_runtime, sra_id):
    """
    Runs an SRA Toolkit container to download FASTQ files for the given SRA dataset.

    Args:
        sra_id (str): The SRA accession number (e.g., SRR12345).
    """
    current_dir = os.getcwd()

    # Ensure Docker/Podman is installed
    try:
        subprocess.run(
            [cont_runtime, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        print(f"Error: {cont_runtime} is not installed or not running.")
        sys.exit(1)

    print(f"Downloading FASTQ data for {sra_id} to {current_dir}...")

    # Run the container and use fasterq-dump
    cmd = [
        cont_runtime,
        "run",
        "--rm",
        "-v",
        f"{current_dir}:/output",
        "ncbi/sra-tools",
        "fasterq-dump",
        "--outdir",
        "/output",
        "--qual-defline",
        "+",
        "--verbose",
        "--progress",
        sra_id,
    ]

    try:
        subprocess.run(cmd, check=True)
        print(
            f"Download complete: {sra_id}_1.fastq, {sra_id}_2.fastq (if paired-end) or {sra_id}.fastq (if single-end)"
        )
    except subprocess.CalledProcessError:
        print(f"Error: Failed to download FASTQ data for {sra_id}")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--container-runtime",
        type=str,
        help="the container runtime to use (docker or podman)",
        choices=["docker", "podman"],
        required=False,
        default="docker",
    )
    parser.add_argument(
        "sra_id", type=str, help="NCBI accession of the dataset to download"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    download_fastq(args.container_runtime, args.sra_id)
