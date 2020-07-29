from .account import account_cli
from .config import config_cli
from .instance import instance_cli
from .main import picomc_cli
from .mod import mod_cli
from .play import play_cli
from .version import version_cli

picomc_cli.add_command(account_cli)
picomc_cli.add_command(config_cli)
picomc_cli.add_command(instance_cli)
picomc_cli.add_command(mod_cli)
picomc_cli.add_command(play_cli)
picomc_cli.add_command(version_cli)
