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


def assert_java(java):
    try:
        jinfo = get_java_info(java)
        badjv = not jinfo["java.version"].startswith("1.8.0")
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

        if badjv:
            logger.warning(
                "Minecraft uses java 1.8.0 by default."
                " You may experience issues, especially with older versions of Minecraft."
            )

        return jinfo

    except FileNotFoundError:
        die(
            "Could not execute java at: {}. Have you installed it? Is it in yout PATH?".format(
                java
            )
        )
