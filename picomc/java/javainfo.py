import os
import shutil
import subprocess
from importlib import resources
from tempfile import TemporaryDirectory

from picomc.logging import logger
from picomc.utils import die

#
# SysDump.class:
#
# import java.io.IOException;
#
# public class SysDump {
#   public static void main(String[] args) throws IOException {
#     System.getProperties().storeToXML(System.out, "");
#   }
# }
#
# Compiled with an antique version of java for widest compatibility.
# Ideally we would distribute the source .java file and build it in the
# picomc build process, but that would bring in a dependency for (old) java
# and extra complexity.
#


def get_java_info(java):
    with TemporaryDirectory() as tmpdir:
        with resources.open_binary("picomc.java", "SysDump.class") as incf, open(
            os.path.join(tmpdir, "SysDump.class"), "wb"
        ) as outcf:
            shutil.copyfileobj(incf, outcf)
        ret = subprocess.run(
            [java, "-cp", ".", "SysDump"], cwd=tmpdir, capture_output=True
        )
    from xml.etree import ElementTree

    xmlstr = ret.stdout.decode("utf8")
    props = ElementTree.fromstring(xmlstr)
    res = dict()
    for entry in props:
        if "entry" != entry.tag or "key" not in entry.attrib:
            continue
        res[entry.attrib["key"]] = entry.text
    return res


def get_major_version(java_version):
    split = java_version.split(".")

    if len(split) == 1:
        # "12", "18-beta", "9-ea", "17-internal"
        first = split[0]
    elif split[0] == "1":
        # "1.8.0_201"
        first = split[1]
    else:
        # "17.0.1"
        first = split[0]

    return first.split("-")[0]


def check_version_against(version: str, wanted):
    wanted_major = str(wanted["majorVersion"])
    running_major = get_major_version(version)

    return wanted_major == running_major


def wanted_to_str(wanted):
    component = wanted["component"]
    major = str(wanted["majorVersion"])

    if component == "jre-legacy":
        return f"1.{major}.0"
    else:
        return str(major)


def assert_java(java, wanted):
    try:
        jinfo = get_java_info(java)
        bitness = jinfo.get("sun.arch.data.model", None)
        if bitness and bitness != "64":
            logger.warning(
                "You are not using 64-bit java. Things will probably not work."
            )

        logger.info(
            "Using java version: {} ({})".format(
                jinfo["java.version"], jinfo["java.vm.name"]
            )
        )

        if not check_version_against(jinfo["java.version"], wanted):
            logger.warning(
                "The version of Minecraft you are launching "
                "uses java {} by default.".format(wanted_to_str(wanted))
            )

            logger.warning(
                "You may experience issues, especially with older versions of Minecraft."
            )

            major = get_major_version(jinfo["java.version"])
            if int(major) < wanted["majorVersion"]:
                logger.error(
                    "Note that at least java {} is required to launch at all.".format(
                        wanted_to_str(wanted)
                    )
                )

        return jinfo

    except FileNotFoundError:
        die(
            "Could not execute java at: {}. Have you installed it? Is it in yout PATH?".format(
                java
            )
        )
