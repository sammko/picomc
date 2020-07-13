import json
import os
import posixpath
import shutil
import urllib.parse
from operator import itemgetter
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
from zipfile import ZipFile

import click
import requests

from picomc.downloader import DownloadQueue
from picomc.logging import logger
from picomc.utils import die

_loader_name = "forge"

MAVEN_URL = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/"
PROMO_FILE = "promotions.json"
META_FILE = "maven-metadata.xml"
INSTALLER_FILE = "forge-{}-installer.jar"
INSTALL_PROFILE_FILE = "install_profile.json"
VERSION_INFO_FILE = "version.json"

FORGE_WRAPPER = {
    "mainClass": "net.cavoj.picoforgewrapper.Main",
    "library": {
        "name": "net.cavoj:PicoForgeWrapper:1.2",
        "downloads": {
            "artifact": {
                "url": f"https://mvn.cavoj.net/net/cavoj/PicoForgeWrapper/1.2/PicoForgeWrapper-1.2.jar",
                "sha1": "e2c52c40ff991133f9515014e9e18e9401ee7959",
                "size": 6383,
            }
        },
    },
}


class VersionError(Exception):
    pass


def get_all_versions():
    resp = requests.get(urllib.parse.urljoin(MAVEN_URL, META_FILE))
    X = ElementTree.fromstring(resp.content)
    return (v.text for v in X.findall("./versioning/versions/"))


def _version_as_tuple(ver):
    return tuple(map(int, ver.split(".")))


def get_applicable_promos(latest=False):
    resp = requests.get(urllib.parse.urljoin(MAVEN_URL, PROMO_FILE))
    promo_obj = resp.json()

    for id_, ver_obj in promo_obj["promos"].items():
        is_latest = id_.endswith("latest")
        if is_latest and not latest:
            continue
        yield ver_obj


def best_version_from_promos(promos, game_version=None):
    if game_version is None:
        bestmcobj = max(promos, key=lambda obj: _version_as_tuple(obj["mcversion"]))
        game_version = bestmcobj["mcversion"]
    versions_for_game = list(
        filter(lambda obj: obj["mcversion"] == game_version, promos)
    )
    if len(versions_for_game) == 0:
        raise VersionError("No forge available for game version. Try using --latest.")
    forge_version = max(
        map(itemgetter("version"), versions_for_game), key=_version_as_tuple
    )

    return game_version, forge_version


def full_from_forge(all_versions, forge_version):
    for v in all_versions:
        gv, fv, *_ = v.split("-")
        if fv == forge_version:
            return gv, v
    raise VersionError(f"Given Forge version ({forge_version}) does not exist")


def resolve_version(game_version=None, forge_version=None, latest=False):
    logger.info("Fetching Forge metadata")
    promos = list(get_applicable_promos(latest))
    all_versions = set(get_all_versions())

    logger.info("Resolving version")

    if forge_version is None:
        game_version, forge_version = best_version_from_promos(promos, game_version)

    found_game, full = full_from_forge(all_versions, forge_version)
    if game_version and found_game != game_version:
        raise VersionError("Version mismatch")
    game_version = found_game

    return f"{game_version}-forge-{forge_version}", full


def install_classic(version_dir, version_name, extract_dir, install_profile):
    # TODO
    die("Legacy forge versions are not yet supported")


def install_113(
    version,
    installer_file,
    version_dir,
    libraries_root,
    version_name,
    extract_dir,
    install_profile,
):
    with open(os.path.join(extract_dir, VERSION_INFO_FILE)) as fd:
        version_info = json.load(fd)
    vspec = {}
    for key in ["arguments", "inheritsFrom", "type", "releaseTime", "time"]:
        vspec[key] = version_info[key]

    vspec["id"] = version_name
    vspec["jar"] = version_info["inheritsFrom"]  # Prevent vanilla jar duplication

    vspec["mainClass"] = FORGE_WRAPPER["mainClass"]
    libs = [FORGE_WRAPPER["library"]]
    libs.extend(version_info["libraries"])

    for install_lib in install_profile["libraries"]:
        install_lib["presenceOnly"] = True
        libs.append(install_lib)

    vspec["libraries"] = libs

    with open(os.path.join(version_dir, f"{version_name}.json"), "w") as fd:
        json.dump(vspec, fd, indent=2)

    shutil.copytree(
        os.path.join(extract_dir, "maven/"), libraries_root, dirs_exist_ok=True
    )

    installer_libpath = os.path.join(
        libraries_root,
        *f"net/minecraftforge/forge/{version}".split("/"),
        INSTALLER_FILE.format(version),
    )
    shutil.copy(installer_file, installer_libpath)


def install(
    versions_root,
    libraries_root,
    game_version=None,
    forge_version=None,
    latest=False,
    version_name=None,
):
    default_version_name, version = resolve_version(game_version, forge_version, latest)

    if version_name is None:
        version_name = default_version_name

    version_dir = os.path.join(versions_root, version_name)
    if os.path.exists(version_dir):
        die(f"Version with name {version_name} already exists")

    for line in (
        "As the Forge project is supported mostly by ads on their downloads\n"
        "site, please consider supporting them at https://www.patreon.com/LexManos/\n"
        "or by downloading the installer manually without AdBlock."
    ).splitlines():
        logger.info(line)

    installer_url = urllib.parse.urljoin(
        MAVEN_URL, posixpath.join(version, INSTALLER_FILE.format(version))
    )
    # TODO Legacy forge versions don't have an installer
    with TemporaryDirectory(prefix=".forge-installer-", dir=versions_root) as tempdir:
        dq = DownloadQueue()
        installer_file = os.path.join(tempdir, "installer.jar")
        dq.add(installer_url, installer_file)
        logger.info("Downloading installer")
        dq.download()
        extract_dir = os.path.join(tempdir, "installer")
        os.mkdir(version_dir)
        os.mkdir(extract_dir)
        with ZipFile(installer_file) as zf:
            zf.extractall(path=extract_dir)
            with open(os.path.join(extract_dir, INSTALL_PROFILE_FILE)) as fd:
                install_profile = json.load(fd)
            if "install" in install_profile:
                install_classic(version_dir, version_name, extract_dir, install_profile)
            else:
                install_113(
                    version,
                    installer_file,
                    version_dir,
                    libraries_root,
                    version_name,
                    extract_dir,
                    install_profile,
                )


@click.group("forge")
def forge_cli():
    pass


@forge_cli.command("install")
@click.option("--name", default=None)
@click.argument("forge_version", required=False)
@click.option("--game", "-g", default=None)
@click.option("--latest", "-l", is_flag=True)
@click.pass_obj
def install_cli(ctxo, name, forge_version, game, latest):
    try:
        install(
            ctxo["VERSIONS_ROOT"],
            ctxo["LIBRARIES_ROOT"],
            game,
            forge_version,
            latest,
            version_name=name,
        )
    except VersionError as e:
        logger.error(e)


def register_cli(root):
    root.add_command(forge_cli)
