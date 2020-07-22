import functools
import os
import posixpath
import urllib.parse

import click

from picomc.cli.utils import pass_version_manager
from picomc.logging import logger
from picomc.utils import die, file_sha1
from picomc.version import VersionType


def version_cmd(fn):
    @click.argument("version_name")
    @pass_version_manager
    @functools.wraps(fn)
    def inner(vm, *args, version_name, **kwargs):
        return fn(*args, version=vm.get_version(version_name), **kwargs)

    return inner


@click.group()
def version_cli():
    """Manage Minecraft versions."""
    pass


@version_cli.command()
@click.option("--release", is_flag=True, default=False)
@click.option("--snapshot", is_flag=True, default=False)
@click.option("--alpha", is_flag=True, default=False)
@click.option("--beta", is_flag=True, default=False)
@click.option("--local", is_flag=True, default=False)
@click.option("--all", is_flag=True, default=False)
@pass_version_manager
def list(vm, release, snapshot, alpha, beta, local, all):
    """List available Minecraft versions."""
    if all:
        release = snapshot = alpha = beta = local = True
    elif not (release or snapshot or alpha or beta):
        logger.info(
            "Showing only locally installed versions. "
            "Use `version list --help` to get more info."
        )
        local = True
    T = VersionType.create(release, snapshot, alpha, beta)
    versions = vm.version_list(vtype=T, local=local)
    print("\n".join(versions))


@version_cli.command()
@version_cmd
@click.option("--verify", is_flag=True, default=False)
def prepare(version, verify):
    """Download required files for the version."""
    version.prepare(verify_hashes=verify)


@version_cli.command()
@version_cmd
@click.argument("which", default="client")
@click.option("--output", default=None)
def jar(version, which, output):
    """Download the file and save."""
    dlspec = version.vspec.downloads.get(which, None)
    if not dlspec:
        die("No such dlspec exists for version {}".format(version.version_name))
    url = dlspec["url"]
    sha1 = dlspec["sha1"]
    ext = posixpath.basename(urllib.parse.urlsplit(url).path).split(".")[-1]
    if output is None:
        output = "{}_{}.{}".format(version.version_name, which, ext)
    if os.path.exists(output):
        die("Refusing to overwrite {}".format(output))
    logger.info("Hash (sha1) should be {}".format(sha1))
    logger.info("Downloading the {} file and saving to {}".format(which, output))
    urllib.request.urlretrieve(dlspec["url"], output)
    if file_sha1(output) != sha1:
        logger.warning("Hash of downloaded file does not match")


def register_version_cli(root_cli):
    root_cli.add_command(version_cli, "version")
