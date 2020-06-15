import os
import posixpath
import urllib.parse

import click

from picomc.env import Env
from picomc.logging import logger
from picomc.utils import die, file_sha1
from picomc.version import VersionType

g_vobj = None


@click.group()
@click.argument("version_name")
def version_cli(version_name):
    """Operate on local Minecraft versions."""
    global g_vobj
    g_vobj = Env.vm.get_version(version_name)


@click.command()
@click.option("--release", is_flag=True, default=False)
@click.option("--snapshot", is_flag=True, default=False)
@click.option("--alpha", is_flag=True, default=False)
@click.option("--beta", is_flag=True, default=False)
@click.option("--local", is_flag=True, default=False)
@click.option("--all", is_flag=True, default=False)
def list_versions(release, snapshot, alpha, beta, local, all):
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
    print("\n".join(Env.vm.version_list(vtype=T, local=local)))


@version_cli.command()
def prepare():
    g_vobj.prepare()


@version_cli.command()
@click.argument("which", default="client")
@click.option("--output", default=None)
def jar(which, output):
    """Download the file and save."""
    dlspec = g_vobj.vspec.downloads.get(which, None)
    if not dlspec:
        die("No such dlspec exists for version {}".format(g_vobj.version_name))
    url = dlspec["url"]
    sha1 = dlspec["sha1"]
    ext = posixpath.basename(urllib.parse.urlsplit(url).path).split(".")[-1]
    if output is None:
        output = "{}_{}.{}".format(g_vobj.version_name, which, ext)
    if os.path.exists(output):
        die("Refusing to overwrite {}".format(output))
    logger.info("Hash (sha1) should be {}".format(sha1))
    logger.info("Downloading the {} file and saving to {}".format(which, output))
    urllib.request.urlretrieve(dlspec["url"], output)
    if file_sha1(output) != sha1:
        logger.warn("Hash of downloaded file does not match")


def register_version_cli(root_cli):
    root_cli.add_command(version_cli, "version")
    root_cli.add_command(list_versions)
