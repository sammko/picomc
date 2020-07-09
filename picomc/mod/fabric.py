import json
import os
import urllib.parse
from datetime import datetime, timezone

import click
import requests

_loader_name = "fabric"

PACKAGE = "net.fabricmc"
MAVEN_BASE = "https://maven.fabricmc.net/"
LOADER_NAME = "fabric-loader"
MAPPINGS_NAME = "intermediary"

__all__ = ["register_cli"]


def latest_game_version():
    url = "https://meta.fabricmc.net/v2/versions/game"
    obj = requests.get(url).json()
    for ver in obj:
        if ver["stable"]:
            return ver["version"]


def get_loader_meta(game_version, loader_version):
    url = "https://meta.fabricmc.net/v2/versions/loader/{}".format(
        urllib.parse.quote(game_version)
    )
    obj = requests.get(url).json()
    for ver in obj:
        if loader_version is None:
            if ver["loader"]["stable"]:
                return ver["loader"]["version"], ver["launcherMeta"]
        else:
            if ver["loader"]["version"] == loader_version:
                return loader_version, ver["launcherMeta"]


def generate_vspec_obj(version_name, loader_obj, loader_version, game_version):
    out = dict()

    out["id"] = version_name
    out["inheritsFrom"] = game_version

    current_time = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    out["time"] = current_time

    mainClass = loader_obj["mainClass"]
    if type(mainClass) is dict:
        mainClass = mainClass["client"]
    out["mainClass"] = mainClass

    libs = []
    for side in ["common", "client"]:
        libs.extend(loader_obj["libraries"][side])

    for artifact, version in [
        (MAPPINGS_NAME, game_version),
        (LOADER_NAME, loader_version),
    ]:
        libs.append(
            {"name": "{}:{}:{}".format(PACKAGE, artifact, version), "url": MAVEN_BASE}
        )

    out["libraries"] = libs

    return out


def install(versions_root, game_version=None, loader_version=None):
    if game_version is None:
        game_version = latest_game_version()

    loader_version, loader_obj = get_loader_meta(game_version, loader_version)

    version_name = "{}-{}-{}".format(LOADER_NAME, loader_version, game_version)

    vspec_obj = generate_vspec_obj(
        version_name, loader_obj, loader_version, game_version
    )

    version_dir = os.path.join(versions_root, version_name)
    assert not os.path.exists(version_dir)

    os.mkdir(version_dir)
    with open(os.path.join(version_dir, f"{version_name}.json"), "w") as fd:
        json.dump(vspec_obj, fd)


@click.command()
@click.argument("game_version", default=False)
@click.argument("loader_version", default=False)
@click.pass_obj
def install_cli(ctxo, game_version, loader_version):
    if game_version is False:
        game_version = None
    if loader_version is False:
        loader_version = None
    install(ctxo["VERSIONS_ROOT"], game_version, loader_version)


def register_cli(root):
    root.add_command(install_cli, name=_loader_name)
