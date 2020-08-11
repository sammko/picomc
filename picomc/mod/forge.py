import json
import os
import posixpath
import shutil
import urllib.parse
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
from zipfile import ZipFile

import click
import requests

from picomc.cli.utils import pass_launcher
from picomc.downloader import DownloadQueue
from picomc.library import Artifact
from picomc.logging import logger
from picomc.utils import Directory

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
        "name": "net.cavoj:PicoForgeWrapper:1.3",
        "downloads": {
            "artifact": {
                "url": "https://mvn.cavoj.net/net/cavoj/PicoForgeWrapper/1.3/PicoForgeWrapper-1.3.jar",
                "sha1": "2c5ed0a503d360b9ebec434a48e1385038b87097",
                "size": 7274,
            }
        },
    },
}


class VersionResolutionError(Exception):
    pass


class AlreadyInstalledError(Exception):
    pass


class InstallationError(Exception):
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
        raise VersionResolutionError(
            "No forge available for game version. Try using --latest."
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
    raise VersionResolutionError(
        f"Given Forge version ({forge_version}) does not exist"
    )


def resolve_version(game_version=None, forge_version=None, latest=False):
    logger.info("Fetching Forge metadata")
    promos = list(get_applicable_promos(latest))
    all_versions = set(get_all_versions())

    logger.info("Resolving version")

    if forge_version is None:
        game_version, forge_version = best_version_from_promos(promos, game_version)

    found_game, full = full_from_forge(all_versions, forge_version)
    if game_version and found_game != game_version:
        raise VersionResolutionError("Version mismatch")
    game_version = found_game

    return game_version, forge_version, full


@dataclass
class ForgeInstallContext:
    version: str  # The full Forge version string
    version_info: dict  # The version.json file from installer package
    game_version: str
    forge_version: str
    version_dir: Path
    libraries_dir: Path
    version_name: str  # Name of the output picomc profile
    extract_dir: Path  # Root of extracted installer
    installer_file: Path
    install_profile: dict


def install_classic(ctx: ForgeInstallContext):
    # TODO Some processing of the libraries should be done to remove duplicates.
    vspec = make_base_vspec(ctx)
    save_vspec(ctx, vspec)
    install_meta = ctx.install_profile["install"]
    src_file = ctx.extract_dir / install_meta["filePath"]
    dst_file = ctx.libraries_dir / Artifact.make(install_meta["path"]).path
    os.makedirs(dst_file.parent, exist_ok=True)
    shutil.copy(src_file, dst_file)


def make_base_vspec(ctx: ForgeInstallContext):
    vi = ctx.version_info
    vspec = {}
    for key in [
        "arguments",
        "minecraftArguments",
        "inheritsFrom",
        "type",
        "releaseTime",
        "time",
        "mainClass",
    ]:
        if key in vi:
            vspec[key] = vi[key]

    vspec["id"] = ctx.version_name
    if "inheritsFrom" in vi:
        vspec["jar"] = vi["inheritsFrom"]  # Prevent vanilla jar duplication
    else:
        # This is the case for som really old forge versions, before the
        # launcher supported inheritsFrom. Libraries should also be filtered
        # in this case, as they contain everything from the vanilla vspec as well.
        # TODO
        logger.warning(
            "Support for this version of Forge is not epic yet. Problems may arise."
        )
        vspec["jar"] = ctx.game_version
        vspec["inheritsFrom"] = ctx.game_version
    vspec["libraries"] = vi["libraries"]

    return vspec


def save_vspec(ctx, vspec):
    with open(ctx.version_dir / f"{ctx.version_name}.json", "w") as fd:
        json.dump(vspec, fd, indent=2)


def copy_libraries(ctx):
    libdir_relative = Artifact.make(ctx.install_profile["path"]).path.parent
    srcdir = ctx.extract_dir / "maven" / libdir_relative
    dstdir = ctx.libraries_dir / libdir_relative
    dstdir.mkdir(parents=True, exist_ok=True)
    for f in srcdir.iterdir():
        shutil.copy2(f, dstdir)


def install_newstyle(ctx: ForgeInstallContext):
    vspec = make_base_vspec(ctx)
    save_vspec(ctx, vspec)
    copy_libraries(ctx)


def install_113(ctx: ForgeInstallContext):
    vspec = make_base_vspec(ctx)

    vspec["libraries"] = [FORGE_WRAPPER["library"]] + vspec["libraries"]
    vspec["mainClass"] = FORGE_WRAPPER["mainClass"]

    for install_lib in ctx.install_profile["libraries"]:
        install_lib["presenceOnly"] = True
        vspec["libraries"].append(install_lib)

    save_vspec(ctx, vspec)

    copy_libraries(ctx)

    installer_descriptor = f"net.minecraftforge:forge:{ctx.version}:installer"
    installer_libpath = ctx.libraries_dir / Artifact.make(installer_descriptor).path
    os.makedirs(installer_libpath.parent, exist_ok=True)
    shutil.copy(ctx.installer_file, installer_libpath)


def install(
    versions_root: Path,
    libraries_root,
    game_version=None,
    forge_version=None,
    latest=False,
    version_name=None,
):
    game_version, forge_version, version = resolve_version(
        game_version, forge_version, latest
    )

    if version_name is None:
        version_name = f"{game_version}-forge-{forge_version}"

    version_dir = os.path.join(versions_root, version_name)
    if os.path.exists(version_dir):
        logger.info(f"Forge {version} already installed as {version_name}")
        raise AlreadyInstalledError(
            version_name, f"Version with name {version_name} already exists"
        )

    logger.info(f"Installing Forge {version} as {version_name}")

    for line in (
        "As the Forge project is kept alive mostly thanks to ads on their downloads\n"
        "site, please consider supporting them at https://www.patreon.com/LexManos/\n"
        "or by visiting their website and looking at some ads."
    ).splitlines():
        logger.warn(line)

    installer_url = urllib.parse.urljoin(
        MAVEN_URL, posixpath.join(version, INSTALLER_FILE.format(version))
    )
    # TODO Legacy forge versions don't have an installer
    with TemporaryDirectory(prefix=".forge-installer-", dir=versions_root) as tempdir:
        tempdir = Path(tempdir)
        installer_file = tempdir / "installer.jar"
        extract_dir = tempdir / "installer"

        dq = DownloadQueue()
        dq.add(installer_url, installer_file)
        logger.info("Downloading installer")
        if not dq.download():
            raise InstallationError("Failed to download installer.")
        os.mkdir(version_dir)
        try:
            os.mkdir(extract_dir)
            ctx = ForgeInstallContext(
                version=version,
                version_info=None,
                game_version=game_version,
                forge_version=forge_version,
                version_dir=versions_root / version_name,
                libraries_dir=libraries_root,
                version_name=version_name,
                extract_dir=extract_dir,
                installer_file=installer_file,
                install_profile=None,
            )
            with ZipFile(installer_file) as zf:
                zf.extractall(path=extract_dir)
                with open(os.path.join(extract_dir, INSTALL_PROFILE_FILE)) as fd:
                    ctx.install_profile = json.load(fd)
                if "install" in ctx.install_profile:
                    ctx.version_info = ctx.install_profile["versionInfo"]
                    logger.info("Installing from classic installer")
                    install_classic(ctx)
                else:
                    with open(os.path.join(extract_dir, VERSION_INFO_FILE)) as fd:
                        ctx.version_info = json.load(fd)
                    if len(ctx.install_profile["processors"]) == 0:
                        logger.info("Installing legacy version from newstyle installer")
                        # A legacy version with an updated installer
                        install_newstyle(ctx)
                    else:
                        logger.info("Installing with PicoForgeWrapper")
                        install_113(ctx)
            logger.info("Done installing Forge")
        except:  # noqa E722
            shutil.rmtree(version_dir, ignore_errors=True)
            raise
    return version_name


@click.group("forge")
def forge_cli():
    """The Forge loader.

    Get more information about Forge at https://minecraftforge.net/"""
    pass


@forge_cli.command("install")
@click.option("--name", default=None)
@click.argument("forge_version", required=False)
@click.option("--game", "-g", default=None)
@click.option("--latest", "-l", is_flag=True)
@pass_launcher
def install_cli(launcher, name, forge_version, game, latest):
    """Installs Forge.

    The best version is selected automatically based on the given parameters.
    By default, only stable Forge versions are considered, use --latest to
    enable beta versions as well.

    You can install a specific version of forge using the FORGE_VERSION argument.
    You can also choose the newest version for a specific version of Minecraft
    using --game."""
    try:
        install(
            launcher.get_path(Directory.VERSIONS),
            launcher.get_path(Directory.LIBRARIES),
            game,
            forge_version,
            latest,
            version_name=name,
        )
    except (VersionResolutionError, InstallationError, AlreadyInstalledError) as e:
        logger.error(e)


@forge_cli.command("version")
@click.argument("forge_version", required=False)
@click.option("--game", "-g", default=None)
@click.option("--latest", "-l", is_flag=True)
def version_cli(forge_version, game, latest):
    """Resolve version without installing."""
    try:
        game_version, forge_version, version = resolve_version(
            game, forge_version, latest
        )
        logger.info(f"Found Forge version {forge_version} for Minecraft {game_version}")
    except VersionResolutionError as e:
        logger.error(e)


def register_cli(root):
    root.add_command(forge_cli)
