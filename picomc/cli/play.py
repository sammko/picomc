import getpass

import click

from picomc.account import AccountError, OfflineAccount, OnlineAccount
from picomc.cli.utils import pass_account_manager, pass_instance_manager, pass_launcher


@click.command()
@click.argument("version", default=False)
@click.option("-a", "--account", "account_name")
@click.option("--verify", is_flag=True, default=False)
@pass_instance_manager
@pass_account_manager
@pass_launcher
def play(launcher, am, im, version, account_name, verify):
    """Play Minecraft without having to deal with stuff"""
    if account_name:
        account = am.get(account_name)
    else:
        try:
            account = am.get_default()
        except AccountError:
            username = input("Choose your account name:\n> ")
            email = input(
                "\nIf you have a mojang account with a Minecraft license,\n"
                "enter your email. Leave blank if you want to play offline:\n> "
            )
            if email:
                account = OnlineAccount.new(username, email)
                password = getpass.getpass("\nPassword:\n> ")
                account.authenticate(password)
            else:
                account = OfflineAccount.new(username)
            am.add(account)
    if not im.exists("default"):
        im.create("default", "latest")
    inst = im.get("default")
    inst.launch(account, version, verify_hashes=verify)


def register_play_cli(picomc_cli):
    picomc_cli.add_command(play)
