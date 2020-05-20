import json
import operator
import os
import posixpath
import re
import shutil
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from functools import reduce
from platform import architecture

import click
import requests
from picomc.downloader import DownloadQueue
from picomc.env import Env, get_filepath
from picomc.logging import logger
from picomc.utils import cached_property, die, file_sha1, file_verify_relative


class VersionType:
    MAP = {"release": 1, "snapshot": 2, "old_alpha": 4, "old_beta": 8}

    def __init__(self, d=None):
        if isinstance(d, int):
            self._a = d
        elif isinstance(d, str):
            self._a = self.MAP[d]

    def __or__(self, other):
        return VersionType(self._a | other._a)

    def match(self, s):
        return bool(self.MAP[s] & self._a)

    @staticmethod
    def create(release, snapshot, alpha, beta):
        a = release | (2 * snapshot) | (4 * alpha) | (8 * beta)
        return VersionType(a)


VersionType.RELEASE = VersionType("release")
VersionType.SNAPSHOT = VersionType("snapshot")
VersionType.ALPHA = VersionType("old_alpha")
VersionType.BETA = VersionType("old_beta")

MODE_OVERRIDE = 0
MODE_REDUCE = 1


class CachedVspecAttr(object):
    def __init__(self, attr, mode=MODE_OVERRIDE, reduce_func=None, default=None):
        self.attr = attr
        self.mode = mode
        self.rfunc = reduce_func
        self.default = default

    def __get__(self, vspec, cls):
        if vspec is None:
            return self
        try:
            if self.mode == MODE_OVERRIDE:
                for v in vspec.chain:
                    if self.attr in v.raw_vspec:
                        r = v.raw_vspec[self.attr]
                        break
                else:
                    raise AttributeError()
            elif self.mode == MODE_REDUCE:
                try:
                    r = reduce(
                        self.rfunc,
                        (
                            v.raw_vspec[self.attr]
                            for v in vspec.chain[::-1]
                            if self.attr in v.raw_vspec
                        ),
                    )
                except TypeError as e:
                    raise AttributeError() from e
        except AttributeError as e:
            if self.default is not None:
                r = self.default(vspec.vobj)
        finally:
            try:
                setattr(vspec, self.attr, r)
                return r
            except UnboundLocalError as e:
                raise AttributeError() from e


def argumentadd(d1, d2):
    d = d1.copy()
    for k, v in d2.items():
        if k in d:
            d[k] += v
        else:
            d[k] = v
    return d


class VersionSpec:
    def __init__(self, vobj):
        self.vobj = vobj
        self.chain = self._resolve_chain()

    def _resolve_chain(self):
        chain = []
        chain.append(self.vobj)
        cv = self.vobj
        while "inheritsFrom" in cv.raw_vspec:
            cv = Version(cv.raw_vspec["inheritsFrom"])
            chain.append(cv)
        return chain

    minecraftArguments = CachedVspecAttr("minecraftArguments")
    arguments = CachedVspecAttr("arguments", mode=MODE_REDUCE, reduce_func=argumentadd)
    mainClass = CachedVspecAttr("mainClass")
    assetIndex = CachedVspecAttr("assetIndex")
    libraries = CachedVspecAttr("libraries", mode=MODE_REDUCE, reduce_func=operator.add)
    jar = CachedVspecAttr("jar", default=lambda vobj: vobj.version_name)
    downloads = CachedVspecAttr("downloads", default=lambda vobj: {})


class Version:
    LIBRARIES_URL = "https://libraries.minecraft.net/"
    ASSETS_URL = "http://resources.download.minecraft.net/"

    def __init__(self, version_name):
        self.version_name = version_name

    @cached_property
    def jarfile(self):
        v = self.vspec.jar
        return get_filepath("versions", v, "{}.jar".format(v))

    @cached_property
    def raw_vspec(self):
        fpath = get_filepath(
            "versions", self.version_name, "{}.json".format(self.version_name)
        )
        ver = Env.vm.get_manifest_version(self.version_name)
        if not ver:
            if os.path.exists(fpath):
                logger.debug("Found custom vspec ({})".format(self.version_name))
                with open(fpath) as fp:
                    return json.load(fp)
            else:
                die("Specified version not available")
        url = ver["url"]
        # Pull the hash out of the url. This is prone to breakage, maybe
        # just try to download the vspec and don't care about whether it
        # is up to date or not.
        url_split = urllib.parse.urlsplit(url)
        sha1 = posixpath.basename(posixpath.dirname(url_split.path))

        if os.path.exists(fpath) and file_sha1(fpath) == sha1:
            logger.debug(
                "Using cached vspec files, hash matches manifest ({})".format(
                    self.version_name
                )
            )
            with open(fpath) as fp:
                return json.load(fp)

        try:
            logger.debug("Downloading vspec file")
            raw = requests.get(url).content
            dirpath = os.path.dirname(fpath)
            os.makedirs(dirpath, exist_ok=True)
            with open(fpath, "wb") as fp:
                fp.write(raw)
            j = json.loads(raw)
            return j
        except requests.ConnectionError:
            die("Failed to retrieve version json file. Check your internet connection.")

    @cached_property
    def vspec(self):
        return VersionSpec(self)

    @cached_property
    def raw_asset_index(self):
        iid = self.vspec.assetIndex["id"]
        url = self.vspec.assetIndex["url"]
        sha1 = self.vspec.assetIndex["sha1"]
        fpath = get_filepath("assets", "indexes", "{}.json".format(iid))
        if os.path.exists(fpath) and file_sha1(fpath) == sha1:
            logger.debug("Using cached asset index, hash matches vspec")
            with open(fpath) as fp:
                return json.load(fp)
        try:
            logger.debug("Downloading new asset index")
            raw = requests.get(url).content
            with open(fpath, "wb") as fp:
                fp.write(raw)
            return json.loads(raw)
        except requests.ConnectionError:
            die("Failed to retrieve asset index.")

    def _libraries(self, natives_only=False):
        # The rule matching in this function could be cached,
        # not sure if worth it.
        for lib in self.vspec.libraries:
            rules = lib.get("rules", [])
            allow = "rules" not in lib
            for rule in rules:
                osmatch = True
                if "os" in rule:
                    osmatch = rule["os"]["name"] == Env.platform
                if osmatch:
                    allow = rule["action"] == "allow"
            if not allow:
                continue
            if natives_only and "natives" not in lib:
                continue
            yield lib

    @staticmethod
    def _resolve_library(lib):
        # TODO
        # For some reason I don't remember, we are constructing the paths
        # to library downloads manually instead of using the url and hash
        # provided in the vspec. This should probably be reworked and hashes
        # should be checked instead of just the filenames.
        #
        # The reason is that the downloads tag is only present in vanilla vspec,
        # forge, optifine, fabric don't provide it.
        suffix = ""
        sha = None
        if "natives" in lib:
            if Env.platform in lib["natives"]:
                suffix = "-" + lib["natives"][Env.platform]
                # FIXME this is an ugly hack
                suffix = suffix.replace("${arch}", architecture()[0][:2])
                try:
                    sha = lib["downloads"]["classifiers"]["natives-" + Env.platform][
                        "sha1"
                    ]
                except KeyError:
                    pass
            else:
                logger.warn(
                    (
                        "Native library ({}) not available"
                        "for current platform ({}). Ignoring."
                    ).format(lib["name"], Env.platform)
                )
                return None
        else:
            try:
                sha = lib["downloads"]["artifact"]["sha1"]
            except KeyError:
                pass

        if sha is None:
            logger.debug("Library {} has no sha in vspec".format(lib["name"]))

        fullname = lib["name"]
        url_base = lib.get("url", Version.LIBRARIES_URL)
        p, n, v, *va = fullname.split(":")
        v2 = "-".join([v] + va)

        # TODO this is fugly
        class LibPaths:
            package = p.replace(".", "/")
            name = n
            version = v
            ext_version = v2
            filename = "{}-{}{}.jar".format(name, ext_version, suffix)
            fullpath = "{}/{}/{}/{}".format(package, name, version, filename)
            url = urllib.parse.urljoin(url_base, fullpath)
            basedir = get_filepath("libraries")
            local_relpath = os.path.join(*fullpath.split("/"))
            local_abspath = os.path.join(basedir, local_relpath)

        LibPaths.sha = sha

        return LibPaths

    def lib_filenames(self, natives=False):
        for lib in self._libraries(natives):
            if not natives and "natives" in lib:
                continue
            paths = self._resolve_library(lib)
            if not paths:
                continue
            yield paths.local_abspath

    def download_jarfile(self, force=False):
        """Checks existence and hash of cached jar. Downloads a new one
        if either condition is violated."""
        logger.debug("Attempting to use jarfile: {}".format(self.jarfile))
        dlspec = self.vspec.downloads.get("client", None)
        if not dlspec:
            logger.debug("jarfile not in dlspec, skipping hash check.")
            if not os.path.exists(self.jarfile):
                logger.error("Jarfile does not exist and can not be downloaded.")
                raise RuntimeError()
            return

        logger.debug("Checking jarfile.")
        if (
            force
            or not os.path.exists(self.jarfile)
            or file_sha1(self.jarfile) != dlspec["sha1"]
        ):
            logger.info("Downloading jar ({}).".format(self.version_name))
            urllib.request.urlretrieve(dlspec["url"], self.jarfile)

    def download_libraries(self, force=False):
        """Downloads missing libraries."""
        logger.info("Checking libraries.")
        q = DownloadQueue()
        for lib in self._libraries():
            paths = self._resolve_library(lib)
            if not paths:
                continue
            ok = (
                os.path.isfile(paths.local_abspath)
                and os.path.getsize(paths.local_abspath) > 0
            )
            if paths.sha is not None:
                ok = ok and file_sha1(paths.local_abspath) == paths.sha
            if force or not ok:
                q.add(paths.url, paths.local_relpath)
        q.download(paths.basedir)

    def _populate_virtual_assets(self, where):
        for name, obj in self.raw_asset_index["objects"].items():
            sha = obj["hash"]
            objpath = get_filepath("assets", "objects", sha[0:2], sha)
            path = os.path.join(where, *name.split("/"))
            # Maybe check file hash first? Would that be faster?
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy(get_filepath(objpath), os.path.join(where, path))

    def get_virtual_asset_path(self):
        return get_filepath("assets", "virtual", self.vspec.assetIndex["id"])

    def prepare_assets_launch(self, gamedir):
        is_map_resources = self.raw_asset_index.get("map_to_resources", False)
        if is_map_resources:
            logger.info("Mapping resources")
            where = os.path.join(gamedir, "resources")
            logger.debug("Resources path: {}".format(where))
            self._populate_virtual_assets(where)

    def download_assets(self, force=False):
        """Downloads missing assets."""

        hashes = set()
        for obj in self.raw_asset_index["objects"].values():
            hashes.add(obj["hash"])

        logger.info("Checking {} assets.".format(len(hashes)))

        is_virtual = self.raw_asset_index.get("virtual", False)

        q = DownloadQueue()
        for sha in hashes:
            path = os.path.join("assets", "objects", sha[0:2], sha)
            if file_verify_relative(path, sha):
                continue
            url = urllib.parse.urljoin(self.ASSETS_URL, posixpath.join(sha[0:2], sha))
            q.add(url, path)

        logger.info("Downloading {} assets. This could take a while.".format(len(q)))
        q.download(Env.app_root)

        if is_virtual:
            logger.info("Copying virtual assets")
            where = self.get_virtual_asset_path()
            logger.debug("Virtual asset path: {}".format(where))
            self._populate_virtual_assets(where)

    def prepare(self):
        self.download_jarfile()
        self.download_libraries()
        self.download_assets()

    def prepare_launch(self, gamedir):
        self.prepare()
        self.prepare_assets_launch(gamedir)


class VersionManager:
    VERSION_MANIFEST_URL = (
        "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    )

    def resolve_version_name(self, v):
        """Takes a metaversion and resolves to a version."""
        if v == "latest":
            v = self.manifest["latest"]["release"]
            logger.info("Resolved latest -> {}".format(v))
        elif v == "snapshot":
            v = self.manifest["latest"]["snapshot"]
            logger.info("Resolved snapshot -> {}".format(v))
        return v

    @cached_property
    def manifest(self):
        manifest_filepath = get_filepath("versions", "manifest.json")
        try:
            m = requests.get(self.VERSION_MANIFEST_URL).json()
            with open(manifest_filepath, "w") as mfile:
                json.dump(m, mfile, indent=4, sort_keys=True)
            return m
        except requests.ConnectionError:
            logger.warn(
                "Failed to retrieve version_manifest. "
                "Check your internet connection."
            )
            try:
                with open(manifest_filepath) as mfile:
                    logger.warn("Using cached version_manifest.")
                    return json.load(mfile)
            except FileNotFoundError:
                logger.warn("Cached version manifest not available.")
                raise RuntimeError("Failed to retrieve version manifest.")

    def get_manifest_version(self, version_name):
        for ver in self.manifest["versions"]:
            if ver["id"] == version_name:
                return ver

    def version_list(self, vtype=VersionType.RELEASE, local=False):
        r = [v["id"] for v in self.manifest["versions"] if vtype.match(v["type"])]
        if local:
            import os

            r += (
                "{} [local]".format(name)
                for name in os.listdir(get_filepath("versions"))
                if os.path.isdir(get_filepath("versions", name))
            )
        return r

    def get_version(self, version_name):
        return Version(self.resolve_version_name(version_name))


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
    logger.info("Hash should be {}".format(sha1))
    logger.info("Downloading the {} file and saving to {}".format(which, output))
    urllib.request.urlretrieve(dlspec["url"], output)
    if file_sha1(output) != sha1:
        logger.warn("Hash of downloaded file does not match")


def register_version_cli(root_cli):
    root_cli.add_command(version_cli, "version")
    root_cli.add_command(list_versions)
