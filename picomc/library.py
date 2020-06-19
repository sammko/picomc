import os
import urllib.parse
from dataclasses import dataclass
from picomc.env import Env
from string import Template

from platform import architecture
from picomc.logging import logger


@dataclass
class LibraryArtifact:
    url: str
    path: str
    sha1: str
    size: int
    filename: str

    @classmethod
    def from_json(cls, obj):
        return cls(
            url=obj["url"],
            path=obj["path"],
            sha1=obj["sha1"],
            size=obj["size"],
            filename=None,
        )


class Library:
    MOJANG_BASE_URL = "https://libraries.minecraft.net/"

    def __init__(self, json_lib):
        self.json_lib = json_lib
        self._populate()

    def _populate(self):
        js = self.json_lib
        self.libname = js["name"]
        self.is_native = "natives" in js
        self.base_url = js.get("url", Library.MOJANG_BASE_URL)

        self.available = True

        self.native_suffix = ""
        if self.is_native:
            try:
                classifier_tmpl = self.json_lib["natives"][Env.platform]
                arch = architecture()[0][:2]
                self.native_classifier = Template(classifier_tmpl).substitute(arch=arch)
                self.native_suffix = "-" + self.native_classifier
            except KeyError:
                logger.warn(
                    f"Native {self.libname} is not available for current platform {Env.platform}."
                )
                self.native_classifier = None
                self.available = False
                return

        self.virt_artifact = self.make_virtual_artifact()
        self.artifact = self.resolve_artifact()

        # Just use filename and path derived from the name.
        self.filename = self.virt_artifact.url
        self.path = self.virt_artifact.path

        # Actual fs path
        self.relpath = os.path.join(*self.path.split("/"))

        if self.artifact:
            final_art = self.artifact

            # Sanity check
            assert self.virt_artifact.path == self.artifact.path
        else:
            final_art = self.virt_artifact

        self.url = final_art.url
        self.sha1 = final_art.sha1
        self.size = final_art.size

    def make_virtual_artifact(self):
        # I don't know where the *va part comes from, it was already implemented
        # before a refactor, unfortunately the reason was not documented.
        # Currently I don't have a version in my versions directory which
        # utilizes that.
        # I am leaving it implemented, as there probably was motivation to do it.
        group, art_id, version, *va = self.libname.split(":")
        group = group.replace(".", "/")
        v2 = "-".join([version] + va)

        filename = f"{art_id}-{v2}{self.native_suffix}.jar"
        path = f"{group}/{art_id}/{version}/{filename}"
        url = urllib.parse.urljoin(self.base_url, path)

        return LibraryArtifact(
            url=url, path=path, sha1=None, size=None, filename=filename
        )

    def resolve_artifact(self):
        if self.is_native:
            if self.native_classifier is None:
                # Native not available for current platform
                return None
            else:
                art = self.json_lib["downloads"]["classifiers"][self.native_classifier]
                return LibraryArtifact.from_json(art)
        else:
            try:
                return LibraryArtifact.from_json(self.json_lib["downloads"]["artifact"])
            except KeyError:
                return None

    def get_abspath(self, library_root):
        return os.path.join(library_root, self.relpath)
