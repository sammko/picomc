import uuid

from picomc.logging import logger
from picomc.yggdrasil import MojangYggdrasil, RefreshError


class NAMESPACE_NULL:
    bytes = b""


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

    def save(self):
        self._am.save(self)

    @classmethod
    def from_config(cls, am, name, config):
        c = OnlineAccount if config.get("online", False) else OfflineAccount
        return c(name=name, _am=am, **config)


class OfflineAccount(Account):
    DEFAULTS = {"uuid": "-", "online": False}
    access_token = "-"

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
        "uuid": "-",
        "online": True,
        "gname": "-",
        "access_token": "-",
        "is_authenticated": False,
        "username": "-",
    }

    fresh = False

    @classmethod
    def new(cls, name, username):
        return cls(name=name, username=username)

    def validate(self):
        r = self._am.yggdrasil.validate(self.access_token)
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
                    refresh = self._am.yggdrasil.refresh(self.access_token)
                    self.access_token, self.uuid, self.gname = refresh
                    self.fresh = True
                    return True
                except RefreshError as e:
                    logger.error(
                        "Failed to refresh access_token," " please authenticate again."
                    )
                    self.is_authenticated = False
                    raise e
                finally:
                    self.save()
        else:
            raise AccountError("Not authenticated.")

    def authenticate(self, password):
        self.access_token, self.uuid, self.gname = self._am.yggdrasil.authenticate(
            self.username, password
        )
        self.is_authenticated = True
        self.fresh = True
        self.save()


class AccountError(ValueError):
    def __str__(self):
        return " ".join(self.args)


DEFAULT_CONFIG = {
    "default": None,
    "accounts": {},
    "client_token": generate_client_token(),
}


class AccountManager:
    CONFIG_FILE = "accounts.json"

    def __init__(self, launcher):
        self.config = launcher.config_manager.get(self.CONFIG_FILE, init=DEFAULT_CONFIG)
        self.yggdrasil = MojangYggdrasil(self.config["client_token"])

    def list(self):
        return self.config["accounts"].keys()

    def get(self, name):
        try:
            acc = Account.from_config(self, name, self.config["accounts"][name])
            acc.is_default = self.config["default"] == name
            return acc
        except KeyError as ke:
            raise AccountError("Account does not exist:", name) from ke

    def exists(self, name):
        return name in self.config["accounts"]

    def get_default(self):
        default = self.config["default"]
        if not default:
            raise AccountError("Default account not configured.")
        return self.get(default)

    def is_default(self, name):
        return name == self.config["default"]

    def set_default(self, account):
        self.config["default"] = account.name

    def add(self, account):
        if self.exists(account.name):
            raise AccountError("An account already exists with that name.")
        if not self.config["default"] and not self.config["accounts"]:
            self.config["default"] = account.name
        self.save(account)

    def save(self, account):
        self.config["accounts"][account.name] = account.to_dict()
        # HACK This doesn't trip the crappy dirty flag on config, set manually
        self.config.dirty = True

    def remove(self, name):
        try:
            if self.config["default"] == name:
                self.config["default"] = None
            del self.config["accounts"][name]
            # HACK This doesn't trip the crappy dirty flag on config, set manually
            self.config.dirty = True
        except KeyError:
            raise AccountError("Account does not exist:", name)
