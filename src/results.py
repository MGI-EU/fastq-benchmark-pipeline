import csv
import dataclasses
import os
from os import path

from src.compat import dataclass
from src.logger import logger
from src.utils import now

RESULTS_DIR_PREFIX = "Results-"
RESULTS_DIR = None


def get_results_dir(parent: str) -> str:
    global RESULTS_DIR

    if RESULTS_DIR:
        return RESULTS_DIR

    while True:
        rdir_name = RESULTS_DIR_PREFIX + now().strftime("%m-%d_%H-%M-%S")
        rdir = path.join(parent, rdir_name)

        if not path.exists(rdir):
            break

    # create and force all permissions to be set
    os.umask(0)
    os.mkdir(rdir)
    os.chmod(rdir, 0o777)

    RESULTS_DIR = rdir
    logger.info(f"Created results folder: {rdir}")

    return RESULTS_DIR


@dataclass(slots=True)
class Result:
    tool: str = ""  # name of the tool
    dataset: str = ""  # name of the dataset
    n_threads: int = 0  # how many threads were used
    original_size: int = 0  # sizes in bytes
    compressed_size: int = 0
    decompressed_size: int = 0
    total_cr: float = 0  # original size (in bytes) divided by all archive files
    ctime: float = 0  # compression time
    dtime: float = 0  # decompression time

    # whether the size of decompressed and original files is the same
    decompressed_same_size: int = 1

    # result is valid if both compression and decompression commands succeeded
    is_valid: bool = True

    def fieldnames(self) -> list[str]:
        return [f.name for f in dataclasses.fields(self)]

    def __bool__(self):
        return self.is_valid

    def __iadd__(self, other):
        if (
            self.tool != other.tool
            or self.dataset != other.dataset
            or self.n_threads != other.n_threads
        ):
            raise ValueError("Merging incompatable results")

        self.ctime += other.ctime
        self.dtime += other.dtime
        self.original_size += other.original_size
        self.compressed_size += other.compressed_size
        self.decompressed_size += other.decompressed_size

        self.is_valid = self.is_valid and other.is_valid
        self.decompressed_same_size = int(
            self.decompressed_same_size and other.decompressed_same_size
        )

        self.total_cr = round(self.original_size / self.compressed_size, 3)
        return self


@dataclass(slots=True)
class GnuTimeStats:
    # TODO: might add other fields later
    elapsed_time: float = 0


def parse_logfile_for_stats(logfile: str) -> GnuTimeStats:
    return GnuTimeStats(elapsed_time=_get_elapsed_time_from_logfile(logfile))


def _get_elapsed_time_from_logfile(logfile: str) -> float:
    with open(logfile, "r") as fin:
        for line in fin:
            line = line.strip()
            if not line.startswith("Elapsed"):
                continue
            timestr = line.split()[-1]
            if timestr.count(":") == 1:  # m:ss
                m, s = map(float, timestr.split(":"))
                return m * 60 + s
            else:  # h:mm:ss
                h, m, s = map(float, timestr.split(":"))
                return h * 3600 + m * 60 + s
        raise ValueError(f"coudn't find Elapsed (wall clock) time in {logfile}")


class ResultWriter:
    # more readable names in the output,
    # e.g. "compression time" instead of "ctime"
    fieldnames_map = {
        "total cr": "compression_ratio",
        "ctime": "compression_time",
        "dtime": "decompression_time",
        "n_threads": "threads",
    }

    fields_to_drop = {"is_valid"}

    def __init__(self, outname):
        self.outname = outname
        self._init_file()

    @property
    def fieldnames(self) -> list[str]:
        all_fields = Result().fieldnames()
        ret = []
        for f in all_fields:
            if f in self.fields_to_drop:
                continue

            try:
                ret.append(self.fieldnames_map[f])
            except KeyError:
                ret.append(f)

        return ret

    def _init_file(self):
        logger.info(f"Writing results to {self.outname}")
        with open(self.outname, "w") as fout:
            writer = csv.DictWriter(
                fout,
                dialect="unix",
                quoting=csv.QUOTE_MINIMAL,
                fieldnames=self.fieldnames,
            )
            writer.writeheader()

    def add_result(self, result: Result):
        result = dataclasses.asdict(result)
        to_write = dict()
        for k, v in result.items():
            if k in self.fields_to_drop:
                continue

            try:
                to_write[self.fieldnames_map[k]] = v
            except KeyError:
                to_write[k] = v

        with open(self.outname, "a") as fout:
            writer = csv.DictWriter(
                fout,
                dialect="unix",
                quoting=csv.QUOTE_MINIMAL,
                fieldnames=self.fieldnames,
            )
            writer.writerow(to_write)
