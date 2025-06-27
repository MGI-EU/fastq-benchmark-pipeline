import enum
import os
import subprocess as sp
from os import path
from typing import Optional

from src.compat import dataclass
from src.logger import logger

HOST_DIR = os.getcwd()
CONTAINER_DIR = "/root"


class ContainerEnv(enum.Enum):
    Common = enum.auto()
    FaStore = enum.auto()


@dataclass(slots=True)
class DockerData:
    image_name: str
    dockerfile: str
    running_container_name: str


DOCKER_DATA = {
    ContainerEnv.Common: DockerData(
        image_name="fastq-compressors",
        dockerfile="dockerfiles/dockerfile_tools",
        running_container_name="running-fastq-compressors",
    ),
    ContainerEnv.FaStore: DockerData(
        image_name="fastore",
        dockerfile="dockerfiles/dockerfile_fastore",
        running_container_name="running-fastore",
    ),
}


@dataclass(slots=True, frozen=True)
class PathConverter:
    """Converts local paths to container paths and vice versa"""

    host_dir: str = HOST_DIR
    container_dir: str = CONTAINER_DIR

    def to_docker(self, p: str) -> str:
        """converts p from path on host to path in container"""

        # things like None or "" mean absent files
        if not p:
            return p

        p = path.abspath(p)
        if not p.startswith(self.host_dir):
            raise ValueError(f"{p} should be an absotule path somewhere in {HOST_DIR}")

        p = p.removeprefix(self.host_dir)
        p = p.removeprefix("/")
        if p:
            return path.join(self.container_dir, p)
        return self.container_dir

    def from_docker(self, p: str):
        """convert p from container path to local"""
        if not p.startswith(self.container_dir):
            raise ValueError(f"{p} should be absolute")

        p = p.removeprefix(self.container_dir)
        p = p.removeprefix("/")
        if p:
            return path.join(self.host_dir, p)
        return self.host_dir

    @property
    def mount_args(self) -> str:
        return f"{self.host_dir}:{self.container_dir}"


class ShellRunner:
    """Executes commands either on the host or in a container"""

    def __init__(self, runtime: str, environ: Optional[ContainerEnv]):
        self.runtime = runtime

        self.prefix = ""
        self.converter = None
        if runtime != "none":
            if not environ:
                raise RuntimeError("must specify environment")

            self.converter = PathConverter()
            self.prefix = " ".join([
                runtime,
                "run",
                "-v",
                self.converter.mount_args,
                "--rm",
                "--name",
                DOCKER_DATA[environ].running_container_name,
                DOCKER_DATA[environ].image_name,
            ])

    def exec_exists(self, binary: str) -> bool:
        """Return True if executable was found"""
        return self.execute(f"which {binary}", gnu_time=False)

    def execute(
        self,
        cmd: str,
        logfile: Optional[str] = None,
        gnu_time: bool = True,
        timeout: int = None,
    ) -> bool:
        """
        Executes cmd, redirecting both stdout and stderr
        to logfile, which must be a path on the host.

        If gnu_time is True, prepends cmd with /usr/bin/time -v.

        Return True if cmd successfuly executed.
        """

        if gnu_time:
            cmd = "/usr/bin/time -v " + cmd

        if logfile:
            logfile_runtime = logfile
            if self.converter:
                logfile_runtime = self.converter.to_docker(logfile)

            cmd += f' > "{logfile_runtime}" 2>&1'

        to_run = (self.prefix + ' sh -c "' + cmd + '"').strip()

        logger.info(to_run)
        try:
            proc = sp.run(to_run, shell=True, capture_output=True, timeout=timeout)
        except sp.TimeoutExpired:
            logger.warning(
                self._make_error_message(f"Timeout {timeout}s expired", proc, logfile)
            )
            return False

        try:
            proc.check_returncode()
        except sp.CalledProcessError:
            logger.warning(
                self._make_error_message("Exited with non-zero code", proc, logfile)
            )
            return False

        return True

    @staticmethod
    def _make_error_message(
        first_line: str, proc: sp.CompletedProcess, logfile: Optional[str] = None
    ) -> str:
        """
        Format:
            <first_line>:
            <proc.stderr>
            Check <logfile> for details.
        """
        msg = first_line

        err = proc.stderr.decode("utf8").rstrip()
        if err:
            msg += ":\n\t" + err

        if logfile and path.exists(logfile):
            msg += f"\n\tCheck {logfile} for details."

        return msg


def image_exists(runtime: str, image_name: str) -> bool:
    """Check if a Docker image exists locally."""
    try:
        to_run = " ".join([runtime, "image", "inspect", image_name])
        logger.info(to_run)

        result = sp.run(to_run, shell=True, text=True, capture_output=True)

        return result.returncode == 0
    except Exception as e:
        logger.warn(f"Error checking image: {e}", exc_info=True)
        return False


def build_images(runtime: str) -> None:
    if runtime == "none":
        return

    # raise execption if runtime is not present
    proc = sp.run([runtime, "--help"], capture_output=True)
    proc.check_returncode()

    for data in DOCKER_DATA.values():
        if not image_exists(runtime, data.image_name):
            logger.info(f"Image {data.image_name} not found. Building...")
            build_image(runtime, data.image_name, data.dockerfile)


def build_image(runtime, image_name, dockerfile):
    """Builds a Docker image from a Dockerfile."""
    if not path.exists(dockerfile):
        raise FileNotFoundError(dockerfile)

    sp.run(
        [
            runtime,
            "build",
            "-t",
            image_name,
            "-f",
            dockerfile,
            path.dirname(dockerfile),
        ],
        check=True,
    )
    logger.info("...build successfully")
