#! /usr/bin/env python
# -*- coding:utf-8 -*-

"""
analyze web fonts (woff2)
"""

import os, sys, re
import datetime
import tempfile
import platform
from fontTools.ttLib import TTFont
from fontTools.ttx import makeOutputFileName

py_ver = sys.version_info[0]    # version of python
platform = platform.system()

def find_all_files(directory):
    for root, dirs, files in os.walk(directory):
        yield root
        for file in files:
            yield os.path.join(root, file)

def get_chrome_cache_dir():
    
    if platform == "Windows":
        return os.path.join(os.getenv("LOCALAPPDATA"), r"Google\Chrome\User Data\Default\Cache")
    else:
        raise NotImplementedError("{} is not supported".format(platform))

def get_firefox_cache_dir():
    if platform == "Windows":
        base = os.path.join(os.getenv("LOCALAPPDATA"), r"Mozilla\Firefox\Profiles")
    else:
        raise NotImplementedError("{} is not supported".format(platform))
    for f in find_all_files(base):
        if os.path.isdir(f) and "cache" in f:
            return f
    return None

# https://github.com/fonttools/fonttools/blob/master/Snippets/woff2_decompress.py
class WoffDecompressor(object):
    def __init__(self, woff):
        self.woff = woff

    def run(self):
        outfilename = self.make_output_name(self.woff)

        font = TTFont(self.woff, recalcBBoxes=False, recalcTimestamp=False)
        font.flavor = None
        font.save(outfilename, reorderTables=True)

        return outfilename

    def make_output_name(self, filename):
        with open(filename, "rb") as f:
            f.seek(4)
            sfntVersion = f.read(4)
        assert len(sfntVersion) == 4, "not enough data"
        ext = '.ttf' if sfntVersion == b"\x00\x01\x00\x00" else ".otf"
        temp_dir = tempfile.mkdtemp()
        outfilename = makeOutputFileName(filename, outputDir=temp_dir, extension=ext)
        return outfilename

class WebfontAnalyzer(object):
    def __init__(self, basedir=get_firefox_cache_dir()):
        self.basedir = basedir

    def run(self):
        for f in find_all_files(self.basedir):
            if os.path.isfile(f) and self.is_recent_file(f) and self.is_woff(f):
                self.analyze_woff(f)

        return 0

    def analyze_woff(self, f):
        decomp = WoffDecompressor(f)
        path = decomp.run()
        font = TTFont(path)
        name = font["name"]
        ok = True
        try:
            name_record = name.getName(nameID=6, platformID=1, platEncID=0)
            encoding = name_record.getEncoding("utf-8")
            s = name_record.string.decode(encoding)
            print(s)
        except Exception as e:
            #print(e)
            ok = False
        if not ok:
            try:
                name_record = name.getName(nameID=6, platformID=3, platEncID=1)
                encoding = name_record.getEncoding("utf-8")
                s = name_record.string.decode(encoding)
                print(s)
            except Exception as e:
                #print(e)
                ok = False

    def is_woff(self, file):
        global py_ver
        if os.path.getsize(file) < 4:
            return False

        with open(file, "rb") as f:
            buf = f.read(4)
            if py_ver == 2:
                return buf[:4] == "wOFF"
            else:
                return buf[0] == ord('w') and buf[1] == ord('O') and buf[2] == ord('F') and buf[3] == ord('F')

    def is_recent_file(self, file):
        now = datetime.datetime.now()
        dt = datetime.datetime.fromtimestamp(os.stat(file).st_mtime)
        elapsed = (now - dt).total_seconds()
        return elapsed < 180

def get_args():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    #parser.add_argument("in_xxx", metavar="XXX", type=str,
    #                    help="input xxx")
    args = parser.parse_args()

    return args

def main():
     args = get_args()
     tool = WebfontAnalyzer()
     sys.exit(tool.run())

if __name__ == "__main__":
    main()
