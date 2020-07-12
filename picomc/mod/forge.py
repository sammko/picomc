import posixpath
import urllib.parse
from operator import itemgetter
from xml.etree import ElementTree

import requests

from picomc.logging import logger

_loader_name = "forge"

MAVEN_URL = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/"
PROMO_FILE = "promotions.json"
META_FILE = "maven-metadata.xml"
INSTALLER_FILE = "forge-{}-installer.jar"


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

    return full


def install(
    versions_root,
    game_version=None,
    forge_version=None,
    latest=False,
    version_name=None,
):
    logger.info(
        "As the Forge project is supported mostly by ads on their downloads\n"
        "site, please consider supporting them at https://www.patreon.com/LexManos/\n"
        "or by downloading the installer manually without AdBlock."
    )
    version = resolve_version(game_version, forge_version, latest)
    installer_url = urllib.parse.urljoin(
        MAVEN_URL, posixpath.join(version, INSTALLER_FILE.format(version))
    )
    print(installer_url)
