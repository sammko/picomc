import subprocess


def java_info(java):
    """Parse the output of `java -XshowSettings:properties -version` and return
    it in a dict."""
    # This while thing is fragile, a better idea is to write a small java program
    # which runs System.getProperties() and serializes the output. This would
    # involve building a java program in the picomc build process, which is
    # not ideal.
    ret = subprocess.run(
        [java, "-XshowSettings:properties", "-version"], capture_output=True
    )
    out = ret.stderr.decode("utf8").splitlines()
    s = 0
    lastkey = None
    D = dict()
    for line in out:
        if s == 0:
            if line == "Property settings:":
                s = 1
        elif s == 1:
            if line == "":
                break
            if line[:4] != "    ":
                # e.g openj9 contains multiline values in some fields.
                L = "    " + line
                nl = True
            else:
                L = line[4:]
                nl = False
            if L[0] == " ":
                if nl:
                    D[lastkey] = D[lastkey] + "\n" + L[4:]
                else:
                    if isinstance(D[lastkey], list):
                        D[lastkey].append(L[4:])
                    else:
                        D[lastkey] = [D[lastkey], L[4:]]
            else:
                lastkey, v = map(str.strip, L.split("="))
                D[lastkey] = v
    if D:
        return D
    else:
        return None


def java_version(java):
    ret = subprocess.run([java, "-version"], capture_output=True)
    return ret.stderr.decode("utf8").splitlines()[0]
