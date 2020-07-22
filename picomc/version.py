import enum
import json
import operator
import os
import posixpath
import shutil
import urllib.parse
import urllib.request
from functools import reduce
from pathlib import PurePath

import requests

from picomc.downloader import DownloadQueue
from picomc.javainfo import get_java_info
from picomc.library import Library
from picomc.logging import logger
from picomc.rules import match_ruleset
from picomc.utils import Directory, die, file_sha1, recur_files


class VersionType(enum.Flag):
    NONE = 0
    RELEASE = enum.auto()
    SNAPSHOT = enum.auto()
    ALPHA = enum.auto()
    BETA = enum.auto()
    ANY = RELEASE | SNAPSHOT | ALPHA | BETA

    def match(self, s):
        names = {
            "release": VersionType.RELEASE,
            "snapshot": VersionType.SNAPSHOT,
            "old_alpha": VersionType.ALPHA,
            "old_beta": VersionType.BETA,
        }
        return bool(names[s] & self)

    @staticmethod
    def create(release, snapshot, alpha, beta):
        D = {
            VersionType.RELEASE: release,
            VersionType.SNAPSHOT: snapshot,
            VersionType.ALPHA: alpha,
            VersionType.BETA: beta,
        }.items()
        return reduce(operator.or_, (k for k, v in D if v), VersionType.NONE)


def argumentadd(d1, d2):
    d = d1.copy()
    for k, v in d2.items():
        if k in d:
            d[k] += v
        else:
            d[k] = v
    return d


_sentinel = object()

LEGACY_ASSETS = {
    "id": "legacy",
    "sha1": "770572e819335b6c0a053f8378ad88eda189fc14",
    "size": 109634,
    "totalSize": 153475165,
    "url": "https://launchermeta.mojang.com/v1/packages/770572e819335b6c0a053f8378ad88eda189fc14/legacy.json",
}


class VersionSpec:
    def __init__(self, vobj, version_manager):
        self.vobj = vobj
        self.chain = self.resolve_chain(version_manager)
        self.initialize_fields()

    def resolve_chain(self, version_manager):
        chain = []
        chain.append(self.vobj)
        cv = self.vobj
        while "inheritsFrom" in cv.raw_vspec:
            cv = version_manager.get_version(cv.raw_vspec["inheritsFrom"])
            chain.append(cv)
        return chain

    def attr_override(self, attr, default=_sentinel):
        for v in self.chain:
            if attr in v.raw_vspec:
                return v.raw_vspec[attr]
        if default is _sentinel:
            raise AttributeError(attr)
        return default

    def attr_reduce(self, attr, reduce_func):
        L = [v.raw_vspec[attr] for v in self.chain[::-1] if attr in v.raw_vspec]
        if not L:
            raise AttributeError(attr)
        return reduce(reduce_func, L)

    def initialize_fields(self):
        try:
            self.minecraftArguments = self.attr_override("minecraftArguments")
        except AttributeError:
            pass
        try:
            self.arguments = self.attr_reduce("arguments", argumentadd)
        except AttributeError:
            pass
        self.mainClass = self.attr_override("mainClass")
        self.assetIndex = self.attr_override("assetIndex", default=None)
        self.assets = self.attr_override("assets", default="legacy")
        if self.assetIndex is None and self.assets == "legacy":
            self.assetIndex = LEGACY_ASSETS
        self.libraries = self.attr_reduce("libraries", lambda x, y: y + x)
        self.jar = self.attr_override("jar", default=self.vobj.version_name)
        self.downloads = self.attr_override("downloads", default={})


class Version:
    ASSETS_URL = "http://resources.download.minecraft.net/"

    def __init__(self, version_name, launcher, version_manifest):
        self.version_name = version_name
        self.launcher = launcher
        self.vm = launcher.version_manager
        self.version_manifest = version_manifest
        self._libraries = dict()

        self.versions_root = self.vm.versions_root
        self.assets_root = self.launcher.get_path(Directory.ASSETS)

        self.raw_vspec = self.get_raw_vspec()
        self.vspec = VersionSpec(self, self.vm)

        if self.vspec.assetIndex is not None:
            self.raw_asset_index = self.get_raw_asset_index(self.vspec.assetIndex)

        self.jarname = self.vspec.jar
        self.jarfile = self.versions_root / self.jarname / "{}.jar".format(self.jarname)

    def get_raw_vspec(self):
        vspec_path = (
            self.versions_root / self.version_name / "{}.json".format(self.version_name)
        )
        if not self.version_manifest:
            if vspec_path.exists():
                logger.debug("Found custom vspec ({})".format(self.version_name))
                with open(vspec_path) as fp:
                    return json.load(fp)
            else:
                die("Specified version ({}) not available".format(self.version_name))
        url = self.version_manifest["url"]
        # Pull the hash out of the url. This is prone to breakage, maybe
        # just try to download the vspec and don't care about whether it
        # is up to date or not.
        url_split = urllib.parse.urlsplit(url)
        sha1 = posixpath.basename(posixpath.dirname(url_split.path))

        if vspec_path.exists() and file_sha1(vspec_path) == sha1:
            logger.debug(
                "Using cached vspec files, hash matches manifest ({})".format(
                    self.version_name
                )
            )
            with open(vspec_path) as fp:
                return json.load(fp)

        try:
            logger.debug("Downloading vspec file")
            raw = requests.get(url).content
            vspec_path.parent.mkdir(parents=True, exist_ok=True)
            with open(vspec_path, "wb") as fp:
                fp.write(raw)
            j = json.loads(raw)
            return j
        except requests.ConnectionError:
            die("Failed to retrieve version json file. Check your internet connection.")

    def get_raw_asset_index(self, asset_index_spec):
        iid = asset_index_spec["id"]
        url = asset_index_spec["url"]
        sha1 = asset_index_spec["sha1"]
        fpath = self.launcher.get_path(Directory.ASSET_INDEXES, "{}.json".format(iid))
        if fpath.exists() and file_sha1(fpath) == sha1:
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

    def get_raw_asset_index_nodl(self, id_):
        fpath = self.launcher.get_path(Directory.ASSET_INDEXES, "{}.json".format(id_))
        if fpath.exists():
            with open(fpath) as fp:
                return json.load(fp)
        else:
            die("Asset index specified in 'assets' not available.")

    def get_libraries(self, java_info):
        if java_info is not None:
            key = java_info.get("java.home", None)
        else:
            key = None
        if key and key in self._libraries:
            return self._libraries[key]
        else:
            libs = []
            for lib in self.vspec.libraries:
                if "rules" in lib and not match_ruleset(lib["rules"], java_info):
                    continue
                lib_obj = Library(lib)
                if not lib_obj.available:
                    continue
                libs.append(lib_obj)
            if key:
                self._libraries[key] = libs
            return libs

    def get_jarfile_dl(self, verify_hashes=False, force=False):
        """Checks existence and hash of cached jar. Returns None if ok, otherwise
        returns download (url, size)"""
        logger.debug("Attempting to use jarfile: {}".format(self.jarfile))
        dlspec = self.vspec.downloads.get("client", None)
        if dlspec is None:
            logger.debug("jarfile dlspec not availble, skipping hash check.")
            if not self.jarfile.exists():
                die("jarfile does not exist and can not be downloaded.")
            return

        logger.debug("Checking jarfile.")
        if (
            force
            or not self.jarfile.exists()
            # The fabric-installer places an empty jarfile here, due to some
            # quirk of an old (git blame 2 years) version of the vanilla launcher.
            # https://github.com/FabricMC/fabric-installer/blob/master/src/main/java/net/fabricmc/installer/client/ClientInstaller.java#L49
            or os.path.getsize(self.jarfile) == 0
            or (verify_hashes and file_sha1(self.jarfile) != dlspec["sha1"])
        ):
            logger.info(
                "Jar file ({}) will be downloaded with libraries.".format(self.jarname)
            )
            return dlspec["url"], dlspec.get("size", None)

    def download_libraries(self, java_info, verify_hashes=False, force=False):
        """Downloads missing libraries."""
        logger.info("Checking libraries.")
        q = DownloadQueue()
        for library in self.get_libraries(java_info):
            if not library.available:
                continue
            basedir = self.launcher.get_path(Directory.LIBRARIES)
            abspath = library.get_abspath(basedir)
            ok = abspath.is_file() and os.path.getsize(abspath) > 0
            if verify_hashes and library.sha1 is not None:
                ok = ok and file_sha1(abspath) == library.sha1
            if not ok and not library.url:
                logger.error(
                    f"Library {library.filename} is missing or corrupt and has no download url."
                )
                continue
            if force or not ok:
                q.add(library.url, library.get_abspath(basedir), library.size)
        jardl = self.get_jarfile_dl(verify_hashes, force)
        if jardl is not None:
            url, size = jardl
            q.add(url, self.jarfile, size=size)
        if len(q) > 0:
            logger.info("Downloading {} libraries.".format(len(q)))
        if not q.download():
            logger.error(
                "Some libraries failed to download. If they are part of a non-vanilla profile, the original installer may need to be used."
            )

    def _populate_virtual_assets(self, asset_index, where):
        for name, obj in asset_index["objects"].items():
            sha = obj["hash"]
            objpath = self.launcher.get_path(Directory.ASSET_OBJECTS, sha[0:2], sha)
            path = where / PurePath(*name.split("/"))
            # Maybe check file hash first? Would that be faster?
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(objpath, path)

    def get_virtual_asset_path(self):
        return self.launcher.get_path(
            Directory.ASSET_VIRTUAL, self.vspec.assetIndex["id"]
        )

    def prepare_assets_launch(self, gamedir):
        launch_asset_index = self.get_raw_asset_index_nodl(self.vspec.assets)
        is_map_resources = launch_asset_index.get("map_to_resources", False)
        if is_map_resources:
            logger.info("Mapping resources")
            where = gamedir / "resources"
            logger.debug("Resources path: {}".format(where))
            self._populate_virtual_assets(launch_asset_index, where)

    def download_assets(self, verify_hashes=False, force=False):
        """Downloads missing assets."""

        hashes = dict()
        for obj in self.raw_asset_index["objects"].values():
            hashes[obj["hash"]] = obj["size"]

        logger.info("Checking {} assets.".format(len(hashes)))

        is_virtual = self.raw_asset_index.get("virtual", False)

        fileset = set(recur_files(self.assets_root))
        q = DownloadQueue()
        objpath = self.launcher.get_path(Directory.ASSET_OBJECTS)
        for sha in hashes:
            abspath = objpath / sha[0:2] / sha
            ok = abspath in fileset  # file exists
            if verify_hashes:
                ok = ok and file_sha1(abspath) == sha
            if force or not ok:
                url = urllib.parse.urljoin(
                    self.ASSETS_URL, posixpath.join(sha[0:2], sha)
                )
                q.add(url, abspath, size=hashes[sha])

        if len(q) > 0:
            logger.info("Downloading {} assets.".format(len(q)))
        if not q.download():
            logger.warning("Some assets failed to download.")

        if is_virtual:
            logger.info("Copying virtual assets")
            where = self.get_virtual_asset_path()
            logger.debug("Virtual asset path: {}".format(where))
            self._populate_virtual_assets(self.raw_asset_index, where)

    def prepare(self, java_info=None, verify_hashes=False):
        if not java_info:
            java_info = get_java_info(self.launcher.global_config.get("java.path"))
        self.download_libraries(java_info, verify_hashes)
        if hasattr(self, "raw_asset_index"):
            self.download_assets(verify_hashes)

    def prepare_launch(self, gamedir, java_info, verify_hahes=False):
        self.prepare(java_info, verify_hahes)
        self.prepare_assets_launch(gamedir)


class VersionManager:
    MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

    def __init__(self, launcher):
        self.launcher = launcher
        self.versions_root = launcher.get_path(Directory.VERSIONS)
        self.manifest = self.get_manifest()

    def resolve_version_name(self, v):
        """Takes a metaversion and resolves to a version."""
        if v == "latest":
            v = self.manifest["latest"]["release"]
            logger.debug("Resolved latest -> {}".format(v))
        elif v == "snapshot":
            v = self.manifest["latest"]["snapshot"]
            logger.debug("Resolved snapshot -> {}".format(v))
        return v

    def get_manifest(self):
        manifest_filepath = self.launcher.get_path(Directory.VERSIONS, "manifest.json")
        try:
            m = requests.get(self.MANIFEST_URL).json()
            with open(manifest_filepath, "w") as mfile:
                json.dump(m, mfile, indent=4, sort_keys=True)
            return m
        except requests.ConnectionError:
            logger.warning(
                "Failed to retrieve version_manifest. "
                "Check your internet connection."
            )
            try:
                with open(manifest_filepath) as mfile:
                    logger.warning("Using cached version_manifest.")
                    return json.load(mfile)
            except FileNotFoundError:
                logger.warning("Cached version manifest not available.")
                raise RuntimeError("Failed to retrieve version manifest.")

    def version_list(self, vtype=VersionType.RELEASE, local=False):
        r = [v["id"] for v in self.manifest["versions"] if vtype.match(v["type"])]
        if local:
            r += sorted(
                "{} [local]".format(path.name)
                for path in self.versions_root.iterdir()
                if not path.name.startswith(".") and path.is_dir()
            )
        return r

    def get_version(self, version_name):
        name = self.resolve_version_name(version_name)
        version_manifest = None
        for ver in self.manifest["versions"]:
            if ver["id"] == name:
                version_manifest = ver
                break
        return Version(name, self.launcher, version_manifest)
