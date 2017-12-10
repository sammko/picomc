import os
import shutil
import subprocess


def downloader_aria2(q, d):
    p = subprocess.Popen('aria2c -i - --auto-file-renaming false --dir'.split()+[d], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    L = []
    for url, outs in q:
        L.append("{}\n out={}".format(url, outs[0]))
    out, err = p.communicate("\n".join(L).encode())
    if p.returncode:
        print(out.decode(), err.decode())
        raise RuntimeError("Failed to download files.")
    else:
        for url, outs in q:
            src = os.path.join(d, outs[0])
            for o in outs[1:]:
                dst = os.path.join(d, o)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)


class DownloadQueue:
    def __init__(self):
        self.q = []

    def add(self, url, *filename):
        self.q.append((url, filename))

    def download(self, d, downloader=downloader_aria2):
        downloader(self.q, d)
