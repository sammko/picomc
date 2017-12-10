import json
import logging
import os
import sys
import urllib
from collections import defaultdict

import click
import requests

from picomc.downloader import DownloadQueue
from picomc.globals import vm
from picomc.utils import file_sha1, get_filepath, get_platform

logger = logging.getLogger('picomc.cli')


class VersionType:
    MAP = {'release': 1, 'snapshot': 2, 'old_alpha': 4, 'old_beta': 8}

    def __init__(self, d=None):
        if isinstance(d, int):
            self._a = d
        elif isinstance(d, str):
            self._a = self.MAP[d]

    def __or__(self, other):
        return VersionType(self._a | other._a)

    def match(self, s):
        return bool(self.MAP[s] & self._a)

    def create(release, snapshot, alpha, beta):
        a = release | (2 * snapshot) | (4 * alpha) | (8 * beta)
        return VersionType(a)


VersionType.RELEASE = VersionType('release')
VersionType.SNAPSHOT = VersionType('snapshot')
VersionType.ALPHA = VersionType('old_alpha')
VersionType.BETA = VersionType('old_beta')


class VersionManager:
    VERSION_MANIFEST = \
        "https://launchermeta.mojang.com/mc/game/version_manifest.json"
    LIBRARIES_URL = "https://libraries.minecraft.net/"
    ASSETS_URL = "http://resources.download.minecraft.net/"

    def __init__(self):
        self._vm = None

    @property
    def manifest(self):
        if not self._vm:
            try:
                self._vm = requests.get(self.VERSION_MANIFEST).json()
                with open(get_filepath('versions/manifest.json'), 'w') as m:
                    json.dump(self._vm, m, indent=4, sort_keys=True)

            except requests.ConnectionError:
                logger.warn("Failed to retrieve version_manifest. "
                            "Check your internet connection.")
                try:
                    with open(get_filepath('versions/manifest.json')) as m:
                        self._vm = json.load(m)
                        logger.warn("Using cached version_manifest.")
                except FileNotFoundError:
                    logger.warn("Cached version_manifest not avaiable.")
                    self._vm = {}
        return self._vm

    def version_json(self, version):
        version = self.resolve_version(version)
        fpath = get_filepath('versions', version, '{}.json'.format(version))
        dirpath = get_filepath('versions', version)
        os.makedirs(dirpath, exist_ok=True)
        if os.path.exists(fpath):
            with open(fpath) as fp:
                return json.load(fp)
        else:
            url = None
            for v in self.manifest['versions']:
                if v['id'] == version:
                    url = v['url']
            if not url:
                raise ValueError("No such version avaiable.")
            try:
                j = requests.get(url).json()
                for l in j['libraries']:
                    try:
                        del l['downloads']
                    except KeyError:
                        pass
                with open(fpath, 'w') as fp:
                    json.dump(j, fp, indent=4, sort_keys=True)
                return j
            except requests.ConnectionError:
                logger.error("Failed to retrieve version json file.")
                sys.exit(1)

    def assets_index(self, iid, url):
        fpath = get_filepath('assets', 'indexes', '{}.json'.format(iid))
        if os.path.exists(fpath):
            with open(fpath) as fp:
                return json.load(fp)
        else:
            try:
                j = requests.get(url).json()
                with open(fpath, 'w') as fp:
                    json.dump(j, fp)
                return j
            except requests.ConnectionError:
                logger.error("Failed to retrieve assets index.")
                sys.exit(1)

    def download_jar(self, jarfile, url):
        urllib.request.urlretrieve(url, jarfile)

    def _get_libraries(self, j, natives_only=False):
        platform = get_platform()
        for lib in j['libraries']:
            rules = lib.get('rules', [])
            allow = 'rules' not in lib
            for rule in rules:
                osmatch = True
                if 'os' in rule:
                    osmatch = rule['os']['name'] == platform
                if osmatch:
                    allow = rule['action'] == 'allow'
            if not allow:
                continue
            if natives_only and 'natives' not in lib:
                continue
            yield lib

    def get_libs(self, version, natives=False):
        j = self.version_json(self.resolve_version(version))
        platform = get_platform()
        for lib in self._get_libraries(j, natives):
            if 'natives' in lib and not natives:
                continue
            suffix = ""
            if 'natives' in lib and platform in lib['natives']:
                suffix = "-" + lib['natives'][platform]
            fullname = lib.get('name')
            package, name, version = fullname.split(":")
            package = package.replace('.', '/')
            filename = "{}-{}{}.jar".format(name, version, suffix)
            fullpath = get_filepath('libraries', package, name,
                                    version, filename)
            yield fullpath

    def download_libraries(self, j):
        platform = get_platform()
        q = DownloadQueue()
        for lib in self._get_libraries(j):
            suffix = ""
            if 'natives' in lib and platform in lib['natives']:
                suffix = "-" + lib['natives'][platform]
            fullname = lib.get('name')
            url_base = lib.get('url', self.LIBRARIES_URL)
            package, name, version = fullname.split(":")
            package = package.replace('.', '/')
            filename = "{}-{}{}.jar".format(name, version, suffix)
            fullpath = "{}/{}/{}/{}".format(package, name, version, filename)
            url = urllib.parse.urljoin(url_base, fullpath)
            output = os.path.join(*fullpath.split('/'))
            if not os.path.exists(get_filepath('libraries', output)):
                q.add(url, output)
        q.download(get_filepath('libraries'))

    def download_assets(self, index, index_url):
        ij = self.assets_index(index, index_url)
        logger.debug("Retrieved index.")
        virtual = ij.get('virtual', False)
        rev = dict()
        for name, obj in ij['objects'].items():
            h = obj['hash']
            if h in rev:
                rev[h].append(name)
            else:
                rev[h] = [name]
        q = DownloadQueue()
        for digest, names in rev.items():
            fname = os.path.join('objects', digest[0:2], digest)
            vfnames = (os.path.join('virtual',
                       'legacy', *name.split('/')) for name in names)
            fullfname = get_filepath('assets', 'objects', digest[0:2], digest)
            url = urllib.parse.urljoin(self.ASSETS_URL,
                                       "{}/{}".format(digest[0:2], digest))
            outs = []
            if not os.path.exists(fullfname):
                outs.append(fname)
            if virtual:
                for vfname in vfnames:
                    if not os.path.exists(get_filepath('assets',
                                          *vfname.split('/'))):
                        outs.append(vfname)
            if outs:
                q.add(url, *outs)

        q.download(get_filepath('assets'))

    def prepare_version(self, version):
        version = self.resolve_version(version)
        j = self.version_json(version)
        dl = j['downloads']['client']
        jarfile = get_filepath('versions', version, '{}.jar'.format(version))
        redownload = False
        if os.path.exists(jarfile):
            if file_sha1(jarfile) != dl['sha1']:
                redownload = True
        else:
            redownload = True
        if redownload:
            logger.info("Downloading jar ({}).".format(version))
            self.download_jar(jarfile, dl['url'])
        logger.info("Downloading libraries")
        self.download_libraries(j)
        logger.info("Downloading assets")
        self.download_assets(j['assetIndex']['id'], j['assetIndex']['url'])

    def version_list(self, vtype=VersionType.RELEASE):
        return [v['id'] for v in self.manifest['versions'] if
                vtype.match(v['type'])]

    def resolve_version(self, v):
        if v == 'latest':
            v = self.manifest['latest']['release']
            logger.info("Resolved latest -> {}".format(v))
        elif v == 'snapshot':
            v = self.manifest['latest']['snapshot']
            logger.info("Resolved snapshot -> {}".format(v))
        return v


@click.group()
def version_cli():
    """Get information about available Minecraft versions."""
    pass


@version_cli.command()
@click.option('--release/--no-release', default=True)
@click.option('--snapshot', is_flag=True, default=False)
@click.option('--alpha', is_flag=True, default=False)
@click.option('--beta', is_flag=True, default=False)
def list(release, snapshot, alpha, beta):
    T = VersionType.create(release, snapshot, alpha, beta)
    print('\n'.join(vm.version_list(vtype=T)))

@version_cli.command()
@click.argument('version')
def prepare(version):
    vm.prepare_version(version)
