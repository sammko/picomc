import logging
import os
import shutil
import subprocess
import zipfile

import click

from picomc.globals import am, vm
from picomc.utils import PersistentConfig, get_filepath, get_platform

logger = logging.getLogger('picomc.cli')


class NativesExtractor:
    def __init__(self, instance):
        self.instance = instance
        self.ndir = get_filepath('instances', instance.name, 'natives')

    def __enter__(self):
        version = self.instance.config.version
        os.makedirs(self.ndir, exist_ok=True)
        dedup = set()
        for fullpath in vm.get_libs(version, natives=True):
            if fullpath in dedup:
                logger.debug("Skipping duplicate natives archive: "
                             "{}".format(fullpath))
                continue
            dedup.add(fullpath)
            logger.debug("Extracting natives archive: {}".format(fullpath))
            with zipfile.ZipFile(fullpath) as zf:
                zf.extractall(path=self.ndir)

    def __exit__(self, ext_type, exc_value, traceback):
        shutil.rmtree(self.ndir)
        # print(self.ndir)


def sanitize_name(name):
    return name.replace('..', '_').replace('/', '_')


def process_arguments(arguments_dict):
    """This is a horrible function the only purpose of which is to die and be
    rewritten from scratch. Along with the native library preprocessor."""
    def match_rule(rule):
        # This launcher currently does not support any of the extended
        # features, which currently include at least:
        #   - is_demo_user
        #   - has_custom_resolution
        # It is not clear whether an `os` and `features` matcher may

        # be present simultaneously - assuming not.
        if 'features' in rule:
            return False

        osmatch = True
        if 'os' in rule:
            # The os matcher may apparently also contain a version spec
            # which is probably a regex matched against the java resported
            # os version. See 17w50a.json for an example. Ignoring it for now.
            # This may lead to older versions of Windows matchins as W10.
            osmatch = rule['os']['name'] == get_platform()
        if osmatch:
            return rule['action'] == 'allow'
        return None

    def subproc(obj):
        args = []
        for a in obj:
            if isinstance(a, str):
                args.append(a)
            else:
                allow = 'rules' not in a
                for rule in a['rules']:
                    m = match_rule(rule)
                    if m is not None:
                        allow = m
                if not allow:
                    continue
                if isinstance(a['value'], list):
                    args.extend(a['value'])
                elif isinstance(a['value'], str):
                    args.append(a['value'])
                else:
                    logger.error("Unknown type of value field.")
        # This is kind of stupid, but dramatically
        # simplifies the subtitution stage. FIXME
        return " ".join(args)
    return (subproc(arguments_dict['game']),
            subproc(arguments_dict['jvm']))


class Instance:
    default_config = {'version': 'latest'}

    def __init__(self, name):
        name = sanitize_name(name)
        self.cfg_file = os.path.join('instances', name, 'config.json')
        self.name = name

    def __enter__(self):
        self.config = PersistentConfig(self.cfg_file,
                                       defaults=self.default_config)
        self.config.__enter__()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.config.__exit__(ext_type, exc_value, traceback)
        del self.config

    def populate(self, version):
        self.config.version = version

    def launch(self, account, version):
        version = version or self.config.version
        vm.prepare_version(version)
        logger.info("Launching instance {}!".format(self.name))
        os.makedirs(
            get_filepath('instances', self.name, 'minecraft'), exist_ok=True)
        with NativesExtractor(self):
            self._exec_mc(account, version)

    def _exec_mc(self, account, version):
        # this is temporary. FIXME
        # This 'function' is quickly getting worse and worse.
        # Rewrite it.

        vjson = vm.version_json(version)
        version = vjson['id']
        java = '/usr/bin/java -Xmx1G'.split()
        libs = list(vm.get_libs(version))
        jarfile = get_filepath('versions', version, '{}.jar'.format(version))
        libs.append(jarfile)
        natives = get_filepath('instances', self.name, 'natives')
        mc = vjson['mainClass']
        gamedir = get_filepath('instances', self.name, 'minecraft')

        if 'minecraftArguments' in vjson:
            mcargs = vjson['minecraftArguments']
            jvmargs = " ".join([
                "-Djava.library.path={}".format(natives), '-cp',
                ':'.join(libs)
            ])  # To match behaviour of process_arguments
        elif 'arguments' in vjson:
            mcargs, jvmargs = process_arguments(vjson['arguments'])
            jvmargs = jvmargs.replace("${", "{")
            jvmargs = jvmargs.format(
                natives_directory=natives,
                launcher_name='picomc',
                launcher_version='0',  # Do something proper here. FIXME.
                classpath=":".join(libs)
            )

        # Convert java-like subtitution strings to python. FIXME.
        mcargs = mcargs.replace("${", "{")

        mcargs = mcargs.format(
            auth_player_name=account.username,
            # Only used in old versions.
            auth_session="token:{}:{}".format(account.get_access_token(),
                                              account.get_uuid()),
            version_name=version,
            game_directory=gamedir,
            assets_root=get_filepath('assets'),
            assets_index_name=vjson['assetIndex']['id'],
            # FIXME Ugly hack relying on untested behaviour:
            game_assets=get_filepath('assets', 'virtual', 'legacy'),
            auth_uuid=account.get_uuid(),
            auth_access_token=account.get_access_token(),
            user_type='mojang',
            version_type='picomc',
            user_properties={}
        )

        fargs = java + jvmargs.split(' ') + [mc] + mcargs.split(' ')
        logger.debug("Launching: " + " ".join(fargs))
        subprocess.run(fargs, cwd=gamedir)

    @classmethod
    def exists(cls, name):
        return os.path.exists(get_filepath('instances', name))


@click.group()
def instance_cli():
    """Manage your instances."""
    pass


@instance_cli.command()
@click.argument('name')
@click.option('--version', default='latest')
def create(name, version):
    if Instance.exists(name):
        logger.error("An instance with that name already exists.")
        return
    with Instance(name) as inst:
        inst.populate(version)


@instance_cli.command()
@click.argument('name')
@click.option('--account', default=None)
@click.option('--version-override', default=None)
def launch(name, account, version):
    if account is None:
        account = am.get_default()
    else:
        account = am.get(account)
    if not Instance.exists(name):
        logger.error("No such instance exists.")
        return
    with Instance(name) as inst:
        inst.launch(account, version)
