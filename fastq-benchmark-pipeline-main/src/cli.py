import argparse
import os
from os import path

from src.tools import ZDUR_MODES, get_names_tools


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-i1",
        "--input1",
        type=argparse.FileType("r"),
        action=FileInSubtree,
        help="fastq-file 1",
        required=True,
    )
    parser.add_argument(
        "-i2",
        "--input2",
        type=argparse.FileType("r"),
        help="fastq-file 2",
        action=FileInSubtree,
        required=False,
        default=None,
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        help="thread count",
        required=False,
        default=4,
    )
    parser.add_argument(
        "-o",
        "--output-folder",
        type=str,
        action=FileInSubtree,
        help="a folder in which to write results",
        required=False,
        default="./",
    )
    parser.add_argument(
        "-r",
        "--repeats",
        type=int,
        help="repeats count",
        required=False,
        default=1,
    )
    parser.add_argument(
        "-s",
        "--suffix",
        type=str,
        help="suffix for output name",
        required=False,
        default="",
    )
    parser.add_argument(
        "--container-runtime",
        type=str,
        help="the container runtime to use (docker or podman), or none if tools are available on the system",
        choices=["docker", "podman", "none"],
        required=False,
        default="docker",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="maximum allowed execution time per tool invocation (in hours)",
        required=False,
        default=48,
    )
    parser.add_argument(
        "--tools",
        type=str,
        help=f'comma-separated list of tools to run or "all"; supported tools: {", ".join(get_names_tools())}',
        required=False,
        default="all",
    )
    parser.add_argument(
        "--zdur-modes",
        type=str,
        help=f"comma-separated list of zDUR compression commands to run; possible values: {', '.join(ZDUR_MODES)}",
        required=False,
        default="c-simtree",
    )

    args = parser.parse_args()

    return args


# As current folder gets mounted, paths to input files
# and to the output folder must be inside of cwd
class FileInSubtree(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        base_dir = os.getcwd()

        if isinstance(values, str):
            arg_path = values
        else:
            arg_path = values.name

        real_path = os.path.realpath(arg_path)

        # Check if the file is within the base directory or its subdirectories
        if not real_path.startswith(base_dir):
            argtype = "Symlink's target" if path.islink(arg_path) else "File"
            raise argparse.ArgumentTypeError(
                f"{argtype} ({real_path}) is outside of cwd ({base_dir})"
            )

        # If valid, set the value as an attribute on the namespace
        setattr(namespace, self.dest, values)
