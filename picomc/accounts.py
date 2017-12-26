import uuid

import click

from picomc.globals import am
from picomc.logging import logger
from picomc.utils import ConfigLoader
from picomc.yggdrasil import AuthenticationError, MojangYggdrasil, RefreshError


class NAMESPACE_NULL:
    bytes = b''


def generate_client_token():
    # Any random string, this matches the behaviour of the official launcher.
    return str(uuid.uuid4().hex)


class Account:
    def __init__(self, **kwargs):
        self.__dict__.update(self.DEFAULTS)
        self.__dict__.update(kwargs)

    def __repr__(self):
        return self.name

    def to_dict(self):
        return {k: getattr(self, k) for k in self.DEFAULTS.keys()}

    @classmethod
    def from_config(cls, name, config):
        c = OnlineAccount if config.get('online', False) else OfflineAccount
        return c(name=name, **config)


class OfflineAccount(Account):
    DEFAULTS = {'uuid': '-', 'online': False}
    access_token = '-'

    @classmethod
    def new(cls, name):
        u = uuid.uuid3(NAMESPACE_NULL, "OfflinePlayer:{}".format(name)).hex
        return cls(name=name, uuid=u)

    @property
    def gname(self):
        return self.name

    def refresh(self):
        return False


class OnlineAccount(Account):
    DEFAULTS = {
        'uuid': '-',
        'online': True,
        'gname': '-',
        'access_token': '-',
        'is_authenticated': False,
        'username': '-'
    }

    fresh = False

    @classmethod
    def new(cls, name, username):
        return cls(name=name, username=username)

    def validate(self):
        r = am.yggdrasil.validate(self.access_token)
        if r:
            self.fresh = True
        return r

    def refresh(self, force=False):
        if self.fresh and not force:
            return False
        if self.is_authenticated:
            if self.validate():
                return
            else:
                try:
                    refresh = am.yggdrasil.refresh(self.access_token)
                    self.access_token, self.uuid, self.gname = refresh
                    self.fresh = True
                    return True
                except RefreshError as e:
                    logger.error("Failed to refresh access_token,"
                                 " please authenticate again.")
                    self.is_authenticated = False
                    raise e
                finally:
                    am.save(self)
        else:
            raise AccountError("Not authenticated.")

    def authenticate(self, password):
        self.access_token, self.uuid, self.gname = am.yggdrasil.authenticate(
            self.username, password)
        self.is_authenticated = True
        self.fresh = True
        am.save(self)


class AccountError(ValueError):
    def __str__(self):
        return " ".join(self.args)


DEFAULT_CONFIG = {
    'default': None,
    'accounts': {},
    'client_token': generate_client_token()
}


class AccountManager:
    cfg_file = 'accounts.json'

    def __enter__(self):
        self._cl = ConfigLoader(self.cfg_file, DEFAULT_CONFIG)
        self.config = self._cl.__enter__()
        self.yggdrasil = MojangYggdrasil(self.config['client_token'])
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self._cl.__exit__(ext_type, exc_value, traceback)
        del self.config
        del self._cl

    def list(self):
        return self.config['accounts'].keys()

    def get(self, name):
        try:
            acc = Account.from_config(name, self.config['accounts'][name])
            acc.is_default = (self.config['default'] == name)
            return acc
        except KeyError as ke:
            raise AccountError("Account does not exist:", name) from ke

    def exists(self, name):
        return name in self.config['accounts']

    def get_default(self):
        default = self.config['default']
        if not default:
            raise AccountError("Default account not configured.")
        return self.get(default)

    def is_default(self, name):
        return name == self.config['default']

    def set_default(self, account):
        self.config['default'] = account.name

    def add(self, account):
        if am.exists(account.name):
            raise AccountError("An account already exists with that name.")
        if not self.config['default'] and not self.config['accounts']:
            self.config['default'] = account.name
        self.save(account)

    def save(self, account):
        self.config['accounts'][account.name] = account.to_dict()

    def remove(self, name):
        try:
            if self.config['default'] == name:
                self.config['default'] = None
            del self.config['accounts'][name]
        except KeyError:
            raise AccountError("Account does not exist:", name)


@click.group()
def accounts_cli():
    """Manage your accounts."""
    pass


@accounts_cli.command()
def list():
    """List avaiable accounts."""
    alist = am.list()
    if alist:
        print("\n".join("{}{}".format('* ' if am.is_default(u) else '  ', u)
                        for u in alist))
    else:
        print("No accounts.")


@accounts_cli.command()
@click.argument('name')
@click.option('--username', '-u', default='')
def create(name, username):
    """Add an account."""
    try:
        if username:
            acc = OnlineAccount.new(name, username)
        else:
            acc = OfflineAccount.new(name)
        am.add(acc)
    except AccountError as e:
        print(e)


@accounts_cli.command()
@click.argument('name')
def authenticate(name):
    import getpass
    try:
        a = am.get(name)
        p = getpass.getpass("Password: ")
        a.authenticate(p)
    except AuthenticationError as e:
        print(e)


@accounts_cli.command()
@click.argument('name')
def refresh(name):
    try:
        a = am.get(name)
        a.refresh()
    except (AccountError, RefreshError) as e:
        print(e)


@accounts_cli.command()
@click.argument('name')
def remove(name):
    try:
        am.remove(name)
    except AccountError as e:
        print(e)


@accounts_cli.command()
@click.argument('name')
def setdefault(name):
    try:
        default = am.get(name)
        am.set_default(default)
    except AccountError as e:
        print(e)
