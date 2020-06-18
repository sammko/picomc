import re
from platform import architecture

from picomc.env import Env
from picomc.logging import logger


def get_os_info(java_info):
    if not java_info:
        return None, None
    version = java_info.get("os.version").decode("ascii")
    arch = java_info.get("os.arch").decode("ascii")
    if not arch:
        arch = {"32": "x86"}.get(architecture()[0][:2], "?")
    return version, arch


def match_rule(rule, java_info):
    # This launcher currently does not support any of the extended
    # features, which currently include at least:
    #   - is_demo_user
    #   - has_custom_resolution
    # It is not clear whether an `os` and `features` matcher may
    # be present simultaneously - assuming not.
    if "features" in rule:
        return False

    if "os" in rule:
        os_version, os_arch = get_os_info(java_info)

        osmatch = True
        if "name" in rule["os"]:
            osmatch = osmatch and rule["os"]["name"] == Env.platform
        if "arch" in rule["os"]:
            osmatch = osmatch and rule["os"]["arch"] == os_arch
        if "version" in rule["os"]:
            osmatch = osmatch and re.match(rule["os"]["version"], os_version)
        return osmatch

    if len(rule) > 1:
        logger.warn("Not matching unknown rule {}".format(rule.keys()))
        return False

    return True


def match_ruleset(ruleset, java_info):
    sat = False
    for rule in ruleset:
        if match_rule(rule, java_info):
            sat = rule["action"] == "allow"
    return sat
