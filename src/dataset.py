from os import path

from src.compat import dataclass
from src.logger import logger


@dataclass(slots=True)
class Dataset:
    name1: str = ""
    name2: str = ""

    def __post_init__(self):
        _check_for_quality_headers(self.name1)
        if self.name2:
            _check_for_quality_headers(self.name2)

    @property
    def name(self) -> str:
        """Name used to refer to this dataset in the output .csv file"""
        base = path.splitext(path.basename(self.name1))[0]
        base += " (PE)" if self.is_pe else " (SE)"
        return base

    @property
    def is_pe(self) -> bool:
        return len(self.name2) != 0

    @property
    def files(self) -> list[str]:
        """Return list of filenames"""
        ret = [self.name1]
        if self.is_pe:
            ret.append(self.name2)
        return ret


def _check_for_quality_headers(fastq: str) -> None:
    with open(fastq, "r") as fin:
        lines = [next(fin).strip() for _ in range(4)]

    qheader = lines[2]
    if len(qheader) != 1:
        logger.warn(
            f"{fastq}:\n"
            f"Found quality headers: {qheader}. They are discarded "
            "by many tools, which will cause difference in size "
            "between the original and decompressed files"
        )
