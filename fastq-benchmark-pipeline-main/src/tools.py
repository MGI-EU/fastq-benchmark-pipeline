import dataclasses
from os import path
from typing import Optional

from src.compat import dataclass
from src.containers import PathConverter
from src.dataset import Dataset
from src.logger import logger


@dataclass(slots=True)
class CompressDecompress:
    """
    Represents pair of commands required to compress and decompress back either a pair of files,
    or a single file in cases where a tool can not directly accept two input files  (like gzip or Leon).

    The commands do not include starting a container or log redirection -
    these needs to be inserted manually.
    """

    original_files: list[str] = dataclasses.field(default_factory=list)
    archive_files: list[str] = dataclasses.field(default_factory=list)
    decompressed_files: list[str] = dataclasses.field(default_factory=list)

    compression: str = ""
    # to run auxiliary tasks in-between compression and decompression
    post_compression: str = ""

    decompression: str = ""
    post_decompression: str = ""

    def original_files_host(self, converter: Optional[PathConverter]):
        yield from _local_paths_gen(self.original_files, converter)

    def archive_files_host(self, converter):
        yield from _local_paths_gen(self.archive_files, converter)

    def decompressed_files_host(self, converter):
        yield from _local_paths_gen(self.decompressed_files, converter)


def _local_paths_gen(paths: list[str], converter: Optional[PathConverter]):
    for p in paths:
        if converter:
            yield converter.from_docker(p)
        else:
            yield p


@dataclass(slots=True)
class Tool:
    name: str = ""  # name of the tool to be report in the output csv
    binary: str = ""  # executable
    commands: list[CompressDecompress] = dataclasses.field(default_factory=list)


ZDUR_MODES = ["c-fast", "c-simtree", "c-stereoseq"]
TOOL_NAMES = {
    "gzip": "gzip",
    "pigz": "pigz",
    "leon": "Leon",
    "quip": "Quip",
    "fqzcomp4": "fqzcomp4",
    "fqzcomp5": "fqzcomp5",
    "dsrc": "DSRC",
    "spring": "SPRING",
    "fastore": "FaStore",
    "repaq": "repaq",
    "zDUR": "zDUR",
}


def get_names_tools():
    return list(TOOL_NAMES.values())


def _filter_tools(all_tools: list[Tool], tools_for_testing: list[str]):
    all_tool_names = TOOL_NAMES.values()
    for testing_tool in tools_for_testing:
        if testing_tool not in all_tool_names:
            logger.warn(f"Unkown tool: {testing_tool}")

    filtered_tools = []
    for tool in all_tools:
        # because for zDUR tool.name is of the form zDUR_{mode}
        key = "zDUR" if tool.name.startswith("zDUR") else tool.name
        if key in tools_for_testing:
            filtered_tools.append(tool)

    return filtered_tools


def get_all_tools(data: Dataset, n_threads: int, zdur_modes: str) -> list[Tool]:
    """Return tools that support running with `n_threads`"""
    if n_threads == 1:
        tools = [
            gzip(data),
            fqzcomp4(data),
            # quip(data)
        ]
    else:
        tools = [pigz(data, n_threads)]

    tools.extend([
        leon(data, n_threads),
        fqzcomp5(data, n_threads),
        dsrc(data, n_threads),
        spring(data, n_threads),
        fastore(data, n_threads),
        repaq(data, n_threads),
    ])

    for zdur_mode in zdur_modes.split(","):
        if zdur_mode not in ZDUR_MODES:
            logger.warn(
                f"Invalid command for zDUR: {zdur_mode}. Should be one of "
                + ", ".join(ZDUR_MODES)
            )
        else:
            tools.append(zdur(data, n_threads, zdur_mode))

    return tools


def get_tools(
    data: Dataset, n_threads: int, tools_for_testing: str, zdur_modes: str
) -> list[Tool]:
    tools = get_all_tools(data, n_threads, zdur_modes)
    if tools_for_testing == "all":
        return tools
    tools_for_testing = tools_for_testing.split(",")

    single_thread_tools = {"gzip", "fqzcomp4", "quip"}
    if n_threads > 1:
        for tool_for_testing in tools_for_testing:
            if tool_for_testing in single_thread_tools:
                logger.warn(f"{tool_for_testing} skipped due to number of threads")
    if n_threads == 1 and "pigz" in tools_for_testing:
        logger.warn("pigz skipped due to number of threads, use gzip for single thread")

    return _filter_tools(tools, tools_for_testing)


def gzip(data: Dataset) -> Tool:
    def make_command(fastq: str) -> CompressDecompress:
        archive = fastq + ".gz"

        # rename archive to achieve decompression
        # to a different name without using -c
        moved_archive = fastq + "_tmp.gz"
        decomp = moved_archive.removesuffix(".gz")

        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f'gzip --keep -f "{fastq}"',
            archive_files=[archive],
            post_compression=f'mv "{archive}" "{moved_archive}"',
            decompression=f'gzip -d --keep -f "{moved_archive}"',
            decompressed_files=[decomp],
            post_decompression=f'rm -f "{moved_archive}"',
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["gzip"], binary="gzip")
    tool.commands = [make_command(data.name1)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2))

    return tool


def pigz(data: Dataset, n_threads: int) -> Tool:
    def make_command(fastq: str) -> CompressDecompress:
        archive = fastq + ".gz"

        # rename archive to achieve decompression
        # to a different name without using -c
        moved_archive = fastq + "_tmp.gz"
        decomp = moved_archive.removesuffix(".gz")

        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f'pigz --keep -f "{fastq}" -p {n_threads}',
            archive_files=[archive],
            post_compression=f'mv "{archive}" "{moved_archive}"',
            decompression=f'pigz -d --keep -f "{moved_archive}" -p {n_threads}',
            decompressed_files=[decomp],
            post_decompression=f'rm -f "{moved_archive}"',
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["pigz"], binary="pigz")
    tool.commands = [make_command(data.name1)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2))

    return tool


def leon(data: Dataset, n_threads: int) -> Tool:
    def make_command(fastq: str, binary: str = "leon") -> CompressDecompress:
        archive = fastq + ".leon"
        archive_qual = fastq + ".qual"
        decomp = path.splitext(fastq)[0] + ".fastq.d"

        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f"{binary} -file {fastq} -c -lossless -nb-cores {n_threads} -verbose 1",
            archive_files=[archive, archive_qual],
            decompression=f"{binary} -file {archive} -d -nb-cores {n_threads} -verbose 1",
            decompressed_files=[decomp],
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["leon"], binary="leon")
    tool.commands = [make_command(data.name1, binary=tool.binary)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2))

    return tool


def quip(data: Dataset) -> Tool:
    def make_command(fastq: str, binary: str = "leon") -> CompressDecompress:
        archive = fastq + ".qp"
        decomp = path.splitext(fastq)[0] + ".fastq.d"

        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f"{binary} {fastq} -o qp",
            archive_files=[archive],
            decompression=f"{binary} {archive}",
            decompressed_files=[decomp],
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["quip"], binary="quip")
    tool.commands = [make_command(data.name1, binary=tool.binary)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2))

    return tool


def fqzcomp4(data: Dataset) -> Tool:
    def make_command(fastq: str, binary: str) -> CompressDecompress:
        archive = fastq + ".fqz4"
        decomp = fastq + ".decomp"

        # -X to disable check sums
        #
        # -P to disable multithreading: it only supports 4 threads:
        # one for each of sequence, quality, header compression,
        # and one for checksum computation, so overall parallelization
        # is not substantial, so let's only test it with 1 thread
        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f"{binary} -X -P {fastq} {archive}",
            archive_files=[archive],
            decompression=f"{binary} -d -X -P {archive} {decomp}",
            decompressed_files=[decomp],
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["fqzcomp4"], binary="fqzcomp")
    tool.commands = [make_command(data.name1, tool.binary)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2, tool.binary))

    return tool


def fqzcomp5(data: Dataset, threads: int) -> Tool:
    def make_command(fastq: str, binary: str) -> CompressDecompress:
        archive = fastq + ".fqz5"
        decomp = archive + ".decomp"

        # -v to increase verbosity
        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f"{binary} -t{threads} -v {fastq} {archive}",
            archive_files=[archive],
            decompression=f"{binary} -d -t{threads} -v {archive} {decomp}",
            decompressed_files=[decomp],
        )

        return cmd

    tool = Tool(name=TOOL_NAMES["fqzcomp5"], binary="fqzcomp5")
    tool.commands = [make_command(data.name1, tool.binary)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2, tool.binary))
    return tool


def dsrc(data: Dataset, threads: int) -> Tool:
    def make_command(fastq: str, binary: str) -> CompressDecompress:
        archive = fastq + ".dsrc"
        decomp = archive + ".decomp"

        # -v to increase verbosity
        cmd = CompressDecompress(
            original_files=[fastq],
            compression=f"{binary} c -v -t{threads} {fastq} {archive}",
            archive_files=[archive],
            decompression=f"{binary} d -v -t{threads} {archive} {decomp}",
            decompressed_files=[decomp],
        )
        return cmd

    tool = Tool(name=TOOL_NAMES["dsrc"], binary="dsrc")
    tool.commands = [make_command(data.name1, tool.binary)]
    if data.is_pe:
        tool.commands.append(make_command(data.name2, tool.binary))

    return tool


def spring(data: Dataset, threads: int) -> Tool:
    tool = Tool(name=TOOL_NAMES["spring"], binary="spring")

    archive = data.name1 + ".spring"
    decomp_files = [archive + ".decomp1"]
    if data.is_pe:
        decomp_files.append(archive + ".decomp2")

    # -r to allow reordering; does not affect compression time,
    # but almost always greatly increases CR
    cmd = CompressDecompress(
        original_files=data.files,
        compression=f"{tool.binary} -c -r -i {' '.join(data.files)} -t{threads} -o {archive}",
        archive_files=[archive],
        decompression=f"{tool.binary} -d -i {archive} -o {' '.join(decomp_files)} -t{threads}",
        decompressed_files=decomp_files,
    )
    tool.commands.append(cmd)

    return tool


def fastore(data: Dataset, threads: int) -> Tool:
    tool = Tool(name=TOOL_NAMES["fastore"], binary="fastore_compress.sh")

    cmd = CompressDecompress()

    archive = data.name1 + ".fastore"
    decomp1 = archive + ".decomp1"
    decomp2 = archive + ".decomp2"

    cmd.archive_files = [archive + ".cdata", archive + ".cmeta"]
    cmd.original_files = data.files

    # --fast becuase according to results from the FaStore paper (and from our own experience),
    # default does not yield much CR improvement, but can be up to 10 slower than --fast
    if data.is_pe:
        cmd.compression = f"fastore_compress.sh --fast --lossless --in {data.name1} --pair {data.name2} --out {archive} --threads {threads} --verbose"
        cmd.decompression = f"fastore_decompress.sh --in {archive} --out {decomp1} --pair {decomp2} --threads {threads} --verbose"
        cmd.decompressed_files = [decomp1, decomp2]
    else:
        cmd.compression = f"fastore_compress.sh --fast --lossless --in {data.name1} --out {archive} --threads {threads} --verbose"
        cmd.decompression = f"fastore_decompress.sh --in {archive} --out {decomp1} --threads {threads} --verbose"
        cmd.decompressed_files = [decomp1]

    tool.commands.append(cmd)
    return tool


def repaq(data: Dataset, threads: int) -> Tool:
    tool = Tool(name=TOOL_NAMES["repaq"], binary="repaq")

    cmd = CompressDecompress()

    archive = data.name1 + ".rqf.xz"  # the extensions are important!
    decomp1 = data.name1 + ".decomp1"
    decomp2 = data.name2 + ".decomp2"

    cmd.archive_files = [archive]
    cmd.original_files = data.files

    if data.is_pe:
        cmd.compression = f"{tool.binary} -c --in1 {data.name1} --in2 {data.name2} -o {archive} -t {threads}"
        cmd.decompression = f"{tool.binary} -d -i {archive} --out1 {decomp1} --out2 {decomp2} -t {threads}"
        cmd.decompressed_files = [decomp1, decomp2]
    else:
        # fmt: off
        cmd.compression = f"{tool.binary} -c --in1 {data.name1} -o {archive} -t {threads}"
        cmd.decompression = f"{tool.binary} -d -i {archive} --out1 {decomp1} -t {threads}"
        cmd.decompressed_files = [decomp1]
        # fmt: on

    tool.commands.append(cmd)
    return tool


def zdur(data: Dataset, threads: int, mode: str = "c-simtree") -> Tool:
    tool = Tool(name=TOOL_NAMES["zDUR"] + f"_{mode}", binary="zDUR")

    cmd = CompressDecompress()

    archive = data.name1 + ".zdur"
    decomp1 = archive + ".decomp1"
    decomp2 = archive + ".decomp2"

    cmd.archive_files = [archive]
    cmd.original_files = data.files

    # --force to ovewrite existent output files
    if data.is_pe:
        cmd.compression = f"{tool.binary} {mode} --i1 {data.name1} --i2 {data.name2} -o {archive} --force --threads {threads}"
        cmd.decompression = f"{tool.binary} d -i {archive} --o1 {decomp1} --o2 {decomp2} --force --threads {threads}"
        cmd.decompressed_files = [decomp1, decomp2]
    else:
        # fmt: off
        cmd.compression = f"{tool.binary} {mode} --i1 {data.name1} -o {archive} --force --threads {threads}"
        cmd.decompression = f"{tool.binary} d -i {archive} --o1 {decomp1} --force --threads {threads}"
        cmd.decompressed_files = [decomp1]
        # fmt: on

    tool.commands.append(cmd)
    return tool
