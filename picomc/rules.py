import re
from platform import architecture

from picomc.env import Env, get_os_arch, get_os_version
from picomc.logging import logger


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
        os_version = get_os_version(java_info)
        os_arch = get_os_arch()

        osmatch = True
        if "name" in rule["os"]:
            osmatch = osmatch and rule["os"]["name"] == Env.platform
        if "arch" in rule["os"]:
            osmatch = osmatch and re.match(rule["os"]["arch"], os_arch)
        if "version" in rule["os"]:
            osmatch = osmatch and re.match(rule["os"]["version"], os_version)
        return osmatch

    if len(rule) > 1:
        logger.warn("Not matching unknown rule {}".format(rule.keys()))
        return False

    return True


def match_ruleset(ruleset, java_info):
    # An empty ruleset is satisfied, but if a ruleset only contains rules which
    # you don't match, it is not.
    if len(ruleset) == 0:
        return True
    sat = False
    for rule in ruleset:
        if match_rule(rule, java_info):
            sat = rule["action"] == "allow"
    return sat
