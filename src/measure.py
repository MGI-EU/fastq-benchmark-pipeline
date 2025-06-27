import copy
import os
from os import path

from src.containers import ContainerEnv, ShellRunner
from src.dataset import Dataset
from src.logger import logger
from src.results import Result, parse_logfile_for_stats
from src.tools import Tool


# all paths are local
# TODO: to many arguments, so maybe write a class instead...
def measure_tool(
    tool: Tool,
    runtime: str,
    data_local: Dataset,
    n_threads: int,
    logfile_prefix: str,
    timeout: int,
) -> Result:
    """
    Paths in data_local and logfile_prefix are local
    """

    environ = ContainerEnv.FaStore if tool.name == "FaStore" else ContainerEnv.Common
    runner = ShellRunner(runtime, environ)

    empty_result = Result(
        tool=tool.name,
        dataset=data_local.name,
        n_threads=n_threads,
    )

    result_total = copy.deepcopy(empty_result)

    if not runner.exec_exists(tool.binary):
        result_total.is_valid = False
        logger.warn(f"{tool.name} not found, skipping...")
        return result_total

    timeout = timeout * 60 * 60

    for idx_cmd, cmd in enumerate(tool.commands):
        result = copy.deepcopy(empty_result)

        logfile = logfile_prefix + f"_compression{idx_cmd + 1}"

        # Compression...
        if not runner.execute(cmd.compression, logfile, timeout=timeout):
            result_total.is_valid = False
            break

        compr_stats = parse_logfile_for_stats(logfile)
        result.ctime = compr_stats.elapsed_time

        # get all original sizes from local paths
        for original_file in cmd.original_files_host(runner.converter):
            result.original_size += path.getsize(original_file)

        # get all compressed sizes (also from local paths)
        for archive_file in cmd.archive_files_host(runner.converter):
            result.compressed_size += path.getsize(archive_file)

        result.total_cr = round(result.original_size / result.compressed_size, 3)

        # Post compression...
        if cmd.post_compression:
            runner.execute(cmd.post_compression, gnu_time=False, timeout=timeout)

        # Decompression...
        logfile = logfile_prefix + f"_decompression{idx_cmd + 1}"
        if not runner.execute(cmd.decompression, logfile, timeout=timeout):
            result_total.is_valid = False
            break

        decompr_stats = parse_logfile_for_stats(logfile)
        result.dtime = decompr_stats.elapsed_time

        # check if size of decompressed files is the same as of original files
        # (and warn, if it's not)
        decompressed_size = 0
        for dfile in cmd.decompressed_files_host(runner.converter):
            decompressed_size += path.getsize(dfile)
        result.decompressed_size = decompressed_size

        if result.original_size != decompressed_size:
            result.decompressed_same_size = 0
            logger.warn(
                f"Size of decompressed files ({decompressed_size}) does not match with the original ({result.original_size})"
            )

        result_total += result

        # Post decompression...
        if cmd.post_decompression:
            runner.execute(cmd.post_decompression, gnu_time=False, timeout=timeout)

        # Cleanup...
        paths_to_remove = list(cmd.archive_files_host(runner.converter)) + list(
            cmd.decompressed_files_host(runner.converter)
        )
        msg = ", ".join(paths_to_remove)
        logger.info("Cleanup: " + msg)
        for p in paths_to_remove:
            if path.exists(p):
                os.unlink(p)

    return result_total
