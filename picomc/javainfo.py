import subprocess


def get_java_info(java):
    """Parse the output of `java -XshowSettings:properties -version` and return
    it in a dict."""
    # This while thing is fragile, a better idea is to write a small java program
    # which runs System.getProperties() and serializes the output. This would
    # involve building a java program in the picomc build process, which is
    # not ideal.
    ret = subprocess.run(
        [java, "-XshowSettings:properties", "-version"], capture_output=True
    )
    out = ret.stderr.splitlines()
    s = 0
    lastkey = None
    D = dict()
    for line in out:
        if s == 0:
            if line == b"Property settings:":
                s = 1
        elif s == 1:
            if line == b"":
                break
            if line[:4] != b"    ":
                # e.g openj9 contains multiline values in some fields.
                L = b"    " + line
                nl = True
            else:
                L = line[4:]
                nl = False
            if L[0:1] == b" ":
                if nl:
                    D[lastkey] = D[lastkey] + b"\n" + L[4:]
                else:
                    if isinstance(D[lastkey], list):
                        D[lastkey].append(L[4:])
                    else:
                        D[lastkey] = [D[lastkey], L[4:]]
            else:
                lastkey, v = map(bytes.strip, L.split(b"="))
                # Take the liberty of assuming the keys are always at least utf8
                lastkey = lastkey.decode("utf-8")
                D[lastkey] = v
    if D:
        return D
    else:
        return None


def get_java_version(java):
    ret = subprocess.run([java, "-version"], capture_output=True)
    return ret.stderr.decode("utf8").splitlines()[0]
