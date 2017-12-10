import uuid

import click

from picomc.globals import am
from picomc.utils import PersistentObject


class NAMESPACE_NULL:
    bytes = b''


class Account:
    def __init__(self, username):
        self.username = username

    def to_dict(self):
        return {}

    def get_uuid(self):
        return uuid.uuid3(NAMESPACE_NULL,
                          "OfflinePlayer:{}".format(self.username)).hex

    def get_access_token(self):
        return '-'


class AccountError(ValueError):
    def __str__(self):
        return " ".join(self.args)


class AccountManager(PersistentObject):
    CONFIG_FILE = 'accounts.json'
    data = {'default': None, 'accounts': {}}

    def list(self):
        return self.data['accounts'].keys()

    def get(self, name):
        try:
            return Account(username=name, **self.data['accounts'][name])
        except KeyError as ke:
            raise AccountError("Account does not exist:", name) from ke

    def exists(self, name):
        return name in self.data['accounts']

    def get_default(self):
        default = self.data['default']
        if not default:
            raise AccountError("Default account not configured.")
        return self.get(default)

    def set_default(self, account):
        self.data['default'] = account.username

    def add(self, account):
        if am.exists(account.username):
            raise AccountError("An account already exists with that name.")
        if not self.data['default'] and not self.data['accounts']:
            self.data['default'] = account.username
        self.data['accounts'][account.username] = account.to_dict()

    def remove(self, name):
        try:
            if self.data['default'] == name:
                self.data['default'] = None
            del self.data['accounts'][name]
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
        prefix = ['  ', '* ']
        print("\n".join("{}{}".format(
            prefix[u == am.data['default']], u) for u in alist))
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
        am.get(username)
        am.data['default'] = username
    except AccountError as e:
        print(e)
