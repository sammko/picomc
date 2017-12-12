import uuid

import click

from picomc.globals import am
from picomc.utils import PersistentConfig


class NAMESPACE_NULL:
    bytes = b''


class Account:
    def __init__(self, username):
        self.username = username
        self.is_default = False

    def to_dict(self):
        return {}

    def get_uuid(self):
        return uuid.uuid3(NAMESPACE_NULL,
                          "OfflinePlayer:{}".format(self.username)).hex

    def get_access_token(self):
        return '-'

    def __repr__(self):
        return self.username


class AccountError(ValueError):
    def __str__(self):
        return " ".join(self.args)


class AccountManager:
    cfg_file = 'accounts.json'
    default_config = {'default': None, 'accounts': {}}

    def __enter__(self):
        self.config = PersistentConfig(self.cfg_file, self.default_config)
        self.config.__enter__()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.config.__exit__(ext_type, exc_value, traceback)
        del self.config

    def list(self):
        return self.config.accounts.keys()

    def get(self, name):
        try:
            acc = Account(username=name, **self.config.accounts[name])
            acc.is_default = (self.config.default == name)
            return acc
        except KeyError as ke:
            raise AccountError("Account does not exist:", name) from ke

    def exists(self, name):
        return name in self.config.accounts

    def get_default(self):
        default = self.config.default
        if not default:
            raise AccountError("Default account not configured.")
        return self.get(default)

    def is_default(self, name):
        return name == self.config.default

    def set_default(self, account):
        self.config.default = account.username

    def add(self, account):
        if am.exists(account.username):
            raise AccountError("An account already exists with that name.")
        if not self.config.default and not self.config.accounts:
            self.config.default = account.username
        self.config.accounts[account.username] = account.to_dict()

    def remove(self, name):
        try:
            if self.config.default == name:
                self.config.default = None
            del self.config.accounts[name]
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
        print("\n".join("{}{}".format(
            '* ' if am.is_default(u) else '  ', u) for u in alist))
    else:
        print("No accounts.")


@accounts_cli.command()
@click.argument('username')
def create(username):
    """Add an account."""
    try:
        am.add(Account(username=username))
    except AccountError as e:
        print(e)


@accounts_cli.command()
@click.argument('username')
def remove(username):
    try:
        am.remove(username)
    except AccountError as e:
        print(e)


@accounts_cli.command()
@click.argument('username')
def setdefault(username):
    try:
        default = am.get(username)
        am.set_default(default)
    except AccountError as e:
        print(e)
