import argparse
import copy
import os
import random
from os import path

from src.containers import PathConverter, build_images
from src.dataset import Dataset
from src.logger import logger
from src.measure import measure_tool
from src.results import ResultWriter, get_results_dir
from src.tools import get_tools


def run(args: argparse.Namespace):
    build_images(args.container_runtime)

    data_local = Dataset(args.input1.name, args.input2.name if args.input2 else "")
    data_cont = copy.deepcopy(data_local)

    if args.container_runtime != "none":
        converter = PathConverter()
        data_cont.name1 = converter.to_docker(data_cont.name1)
        data_cont.name2 = converter.to_docker(data_cont.name2)

    results_dir = get_results_dir(parent=args.output_folder)
    logdir = path.join(results_dir, "logs")
    os.mkdir(logdir)

    tools = get_tools(data_cont, args.threads, args.tools, args.zdur_modes)
    if len(set(t.name for t in tools)) != len(tools):
        raise RuntimeError("Duplicated tool names are not allowed")

    writer = ResultWriter(path.join(results_dir, "benchmark_results.csv"))

    for iteration in range(1, args.repeats + 1):
        random.shuffle(tools)  # execute in random order (just in case)

        logger.info("Scheduled order: " + ", ".join([tool.name for tool in tools]))

        for tool in tools:
            logger.info(f"Iteration {iteration} for {tool.name}")
            logfile_prefix = path.join(logdir, f"{tool.name}_iter{iteration}")
            result = measure_tool(
                tool,
                args.container_runtime,
                data_local,
                args.threads,
                logfile_prefix,
                args.timeout,
            )

            if result:
                writer.add_result(result)
            else:
                logger.warn(f"Results for {tool.name} are invalid")
