import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from picomc.account import OnlineAccount
from picomc.launcher import Launcher


class CompletionContext:
    def __init__(self, estack, cli_args):
        root = os.getenv("PICOMC_ROOT")
        if root is not None:
            root = Path(root)
        self.launcher = Launcher(estack, root)

    @classmethod
    @contextmanager
    def new(cls, cli_args):
        with ExitStack() as es:
            yield cls(es, cli_args)

    def list_instances(self, incomplete):
        return [i for i in self.launcher.instance_manager.list() if incomplete in i]

    def list_accounts(self, incomplete, online_only):
        am = self.launcher.account_manager
        for a in am.list():
            if incomplete not in a:
                continue
            if online_only:
                if not isinstance(am.get(a), OnlineAccount):
                    continue
            yield a
