# This files comes from a heavily modified version of miniver.
# https://github.com/jbweston/miniver
import os
from distutils.command.build_py import build_py as build_py_orig

from setuptools.command.sdist import sdist as sdist_orig

VERSION_FILE = "_version.py"


# Loads _version.py module without importing the whole package.
def get_version(package_name):
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("version", os.path.join(package_name, "_version.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__version__


def _write_version(fname, version):
    # This could be a hard link, so try to delete it first.  Is there any way
    # to do this atomically together with opening?
    try:
        os.remove(fname)
    except OSError:
        pass
    with open(fname, "w") as f:
        f.write(
            "# This file has been created by setup.py.\n"
            "__version__ = '{}'\n".format(version)
        )


def make_cmdclass(package_name, version):
    class _build_py(build_py_orig):
        def run(self):
            super().run()
            _write_version(
                os.path.join(self.build_lib, package_name, VERSION_FILE), version
            )

    class _sdist(sdist_orig):
        def make_release_tree(self, base_dir, files):
            super().make_release_tree(base_dir, files)
            _write_version(os.path.join(base_dir, package_name, VERSION_FILE), version)

    return dict(sdist=_sdist, build_py=_build_py)


def make_version_cmdclass(package_name):
    version = get_version(package_name)
    return version, make_cmdclass(package_name, version)
