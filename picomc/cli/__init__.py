from .account import register_account_cli
from .config import register_config_cli
from .instance import register_instance_cli
from .main import picomc_cli
from .mod import register_mod_cli
from .play import register_play_cli
from .version import register_version_cli

register_account_cli(picomc_cli)
register_version_cli(picomc_cli)
register_instance_cli(picomc_cli)
register_config_cli(picomc_cli)
register_mod_cli(picomc_cli)
register_play_cli(picomc_cli)
