from operator import itemgetter
from pathlib import Path, PurePath

import click
import requests

from picomc.cli.utils import pass_instance_manager, pass_launcher
from picomc.downloader import DownloadQueue
from picomc.logging import logger
from picomc.mod import forge
from picomc.utils import Directory, die, sanitize_name

BASE_URL = "https://api.modpacks.ch/"
MODPACK_URL = BASE_URL + "public/modpack/{}"
VERSION_URL = MODPACK_URL + "/{}"


class FTBError(Exception):
    pass


class InvalidVersionError(FTBError):
    pass


class APIError(FTBError):
    pass


def get_pack_manifest(pack_id):
    resp = requests.get(MODPACK_URL.format(pack_id))
    resp.raise_for_status()
    j = resp.json()
    if j["status"] == "error":
        raise APIError(j["message"])
    return j


def get_version_manifest(pack_id, version_id):
    resp = requests.get(VERSION_URL.format(pack_id, version_id))
    resp.raise_for_status()
    j = resp.json()
    if j["status"] == "error":
        raise APIError(j["message"])
    return j


def resolve_pack_meta(pack: str, pack_version=None, use_beta=False):
    if pack.isascii() and pack.isdecimal():
        # We got pack ID
        pack_id = int(pack)
    else:
        # We got pack slug
        raise NotImplementedError(
            "Pack slug resolution is currently not available. Please use the numerical pack ID."
        )

    pack_manifest = get_pack_manifest(pack_id)

    if pack_version is not None:
        for version in pack_manifest["versions"]:
            if version["name"] == pack_version:
                version_id = version["id"]
                break
        else:
            raise InvalidVersionError(pack_version)
    else:

        def filt(v):
            return use_beta or v["type"] == "Release"

        filtered_versions = filter(filt, pack_manifest["versions"])
        version_id = max(filtered_versions, key=itemgetter("updated"))["id"]

    return pack_manifest, get_version_manifest(pack_id, version_id)


def install(pack_id, version, launcher, im, instance_name, use_beta):
    try:
        pack_manifest, version_manifest = resolve_pack_meta(pack_id, version, use_beta)
    except NotImplementedError as ex:
        die(ex)

    pack_name = pack_manifest["name"]
    pack_version = version_manifest["name"]

    if instance_name is None:
        instance_name = sanitize_name(f"{pack_name}-{pack_version}")

    if im.exists(instance_name):
        die("Instance {} already exists".format(instance_name))

    logger.info(f"Installing {pack_name} {pack_version} as {instance_name}")

    forge_version_name = None
    game_version = None
    for target in version_manifest["targets"]:
        if target["name"] == "forge":
            try:
                forge_version_name = forge.install(
                    versions_root=launcher.get_path(Directory.VERSIONS),
                    libraries_root=launcher.get_path(Directory.LIBRARIES),
                    forge_version=target["version"],
                )
            except forge.AlreadyInstalledError as ex:
                forge_version_name = ex.args[0]
        elif target["name"] == "minecraft":
            game_version = target["version"]
        else:
            logger.warn(f"Skipping unsupported target {target['name']}")

    inst_version = forge_version_name or game_version

    inst = im.create(instance_name, inst_version)
    inst.config["java.memory.max"] = str(version_manifest["specs"]["recommended"]) + "M"

    mcdir: Path = inst.get_minecraft_dir()
    dq = DownloadQueue()
    for f in version_manifest["files"]:
        filepath: Path = mcdir / PurePath(f["path"]) / f["name"]
        filepath.parent.mkdir(exist_ok=True, parents=True)
        dq.add(f["url"], filepath, f["size"])

    logger.info("Downloading modpack files")
    dq.download()

    logger.info(f"Installed successfully as {instance_name}")


@click.group("ftb")
def ftb_cli():
    """Handles modern FTB modpacks"""
    pass


@ftb_cli.command("install")
@click.argument("pack_id")
@click.argument("version", required=False)
@click.option("--name", "-n", default=None, help="Name of the resulting instance")
@click.option("--beta", "-b", is_flag=True, help="Consider beta modpack versions")
@pass_instance_manager
@pass_launcher
def install_cli(launcher, im, pack_id, name, version, beta):
    """Install an FTB modpack.

    An instance is created with the correct version of forge selected and all
    the mods from the pack installed.

    PACK_ID can be the numeric id of the FTB modpack or the slug from the URL to its
    website.

    VERSION is the version name, for example 2.1.3, not its ID. If VERSION is not
    specified, the latest is automatically chosen. If --beta is used, the chosen
    version can be a beta version. Otherwise, only stable versions are considered."""
    install(pack_id, version, launcher, im, name, use_beta=beta)


def register_cli(root):
    root.add_command(ftb_cli)
