# This files comes from a heavily modified version of miniver.
# https://github.com/jbweston/miniver
import os
from collections import namedtuple

Version = namedtuple("Version", ("release", "dev", "labels"))

__all__ = ["__version__"]

package_root = os.path.dirname(os.path.realpath(__file__))
package_name = os.path.basename(package_root)
distr_root = os.path.dirname(package_root)

_refnames = "$Format:%D$"
_git_hash = "$Format:%h$"


def get_version():
    # This code does not exist in sdist or bdist, so we are in git
    # or a git archive.
    if _refnames.startswith("$Format"):
        # git
        version = get_version_from_git()
    else:
        # git archive
        version = get_version_from_git_archive()

    return pep440_format(version)


def pep440_format(version_info):
    release, dev, labels = version_info

    local_parts = []
    if dev:
        local_parts.append(dev)

    if labels:
        local_parts.extend(labels)

    local_suffix = ""
    if local_parts:
        local_suffix = "+" + ".".join(local_parts)

    return release + local_suffix


def get_version_from_git():
    import subprocess

    p = subprocess.Popen(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=distr_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ret = p.wait()
    if ret != 0:
        raise RuntimeError("git rev-parse:", ret)
    if not os.path.samefile(p.communicate()[0].decode().rstrip("\n"), distr_root):
        # The top-level directory of the current Git repository is not the same
        # as the root directory of the distribution: do not extract the
        # version from Git.
        raise RuntimeError("git top-level different from dist root")

    # git describe --first-parent does not take into account tags from branches
    # that were merged-in. The '--long' flag gets us the 'dev' version and
    # git hash, '--always' returns the git hash even if there are no tags.
    for opts in [["--first-parent"], []]:
        p = subprocess.Popen(
            ["git", "describe", "--long", "--always"] + opts,
            cwd=distr_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if p.wait() == 0:
            break
    else:
        raise RuntimeError("git describe failed")

    description = (
        p.communicate()[0]
        .decode()
        .strip("v")  # Tags can have a leading 'v', but the version should not
        .rstrip("\n")
        .rsplit("-", 2)  # Split the latest tag, commits since tag, and hash
    )

    try:
        release, dev, git = description
    except ValueError:  # No tags, only the git hash
        # prepend 'g' to match with format returned by 'git describe'
        git = "g{}".format(*description)
        release = "unknown"
        dev = None

    labels = []
    if dev == "0":
        dev = None
    else:
        labels.append(git)

    try:
        p = subprocess.Popen(["git", "diff", "--quiet"], cwd=distr_root)
    except OSError:
        labels.append("confused")  # This should never happen.
    else:
        if p.wait() == 1:
            labels.append("dirty")

    return Version(release, dev, labels)


def get_version_from_git_archive():
    VTAG = "tag: v"
    refs = set(r.strip() for r in _refnames.split(","))
    version_tags = set(r[len(VTAG) :] for r in refs if r.startswith(VTAG))
    if version_tags:
        # This should be sorted using packaging.version.parse but
        # a single commit should not have multiple versions anyway.
        release, *_ = sorted(version_tags)
        return Version(release, dev=None, labels=None)
    else:
        print("Versions don't work in non-release git archives. Clone the repo.")
        return Version("unknown", dev=None, labels=["g{}".format(_git_hash)])


__version__ = get_version()
