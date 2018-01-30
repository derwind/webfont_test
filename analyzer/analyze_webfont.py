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
    elif platform == "Darwin":
        # Library/Caches/com.google.chrome ?
        return os.path.join(os.getenv("HOME"), r"Library/Application Support/Google/Chrome/Default/Application Cache")
    else:
        raise NotImplementedError("{} is not supported".format(platform))

def get_firefox_cache_dirs():
    if platform == "Windows":
        base = os.path.join(os.getenv("LOCALAPPDATA"), r"Mozilla\Firefox\Profiles")
    elif platform == "Darwin":
        base = os.path.join(os.getenv("HOME"), r"Library/Caches/Firefox/Profiles")
    else:
        raise NotImplementedError("{} is not supported".format(platform))
    dirs = set()
    for f in find_all_files(base):
        if os.path.isdir(f) and ("cache" in f or "Cache" in f):
            dirs.add(f)
    return dirs

class GsubAnalyzer(object):
    def __init__(self, font_path):
        self.font = TTFont(font_path)
        self.gsub = self.font["GSUB"]
        self.lang_system = {}
        self.lookup_indexes = []
        self.features = set()

    def analyze(self):
        self._analyze_script()
        for script_tag in self.lang_system.keys():
            for lang_sys_tag in self.lang_system[script_tag].keys():
                feature_indexes = self.lang_system[script_tag][lang_sys_tag]
                feature_records = [self.gsub.table.FeatureList.FeatureRecord[idx] for idx in feature_indexes]
                for record in feature_records:
                    self.features.add(record.FeatureTag)

    def _analyze_script(self):
        for record in self.gsub.table.ScriptList.ScriptRecord:
            self.lang_system[record.ScriptTag] = {}
            self.lang_system[record.ScriptTag]["dflt"] = [idx for idx in record.Script.DefaultLangSys.FeatureIndex]
            for lang_record in record.Script.LangSysRecord:
                self.lang_system[record.ScriptTag][lang_record.LangSysTag] = [idx for idx in lang_record.LangSys.FeatureIndex]

class GposAnalyzer(object):
    def __init__(self, font_path):
        self.font = TTFont(font_path)
        self.gpos = self.font["GPOS"]
        self.lang_system = {}
        self.lookup_indexes = []
        self.features = set()

    def analyze(self):
        self._analyze_script()
        for script_tag in self.lang_system.keys():
            for lang_sys_tag in self.lang_system[script_tag].keys():
                feature_indexes = self.lang_system[script_tag][lang_sys_tag]
                feature_records = [self.gpos.table.FeatureList.FeatureRecord[idx] for idx in feature_indexes]
                for record in feature_records:
                    self.features.add(record.FeatureTag)

    def _analyze_script(self):
        for record in self.gpos.table.ScriptList.ScriptRecord:
            self.lang_system[record.ScriptTag] = {}
            self.lang_system[record.ScriptTag]["dflt"] = [idx for idx in record.Script.DefaultLangSys.FeatureIndex]
            for lang_record in record.Script.LangSysRecord:
                self.lang_system[record.ScriptTag][lang_record.LangSysTag] = [idx for idx in lang_record.LangSys.FeatureIndex]

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
    def __init__(self, basedirs=None):
        if basedirs is None:
            basedirs=get_firefox_cache_dirs()
        self.basedirs = basedirs

    def run(self):
        for basedir in self.basedirs:
            for f in find_all_files(basedir):
                if os.path.isfile(f) and self.is_recent_file(f) and self.is_woff(f):
                    self.analyze_woff(f)

        return 0

    def analyze_woff(self, woff):
        decomp = WoffDecompressor(woff)
        font_path = decomp.run()
        font = TTFont(font_path)
        font_name = self.get_font_name(font)

        print("[{}]".format(font_name))
        if "GSUB" in font:
            gsub = GsubAnalyzer(font_path)
            gsub.analyze()
            print("  GSUB: {}".format(",".join(sorted(gsub.features))))
        if "GPOS" in font:
            gpos = GposAnalyzer(font_path)
            gpos.analyze()
            print("  GPOS: {}".format(",".join(sorted(gpos.features))))

    def get_font_name(self, font):
        name = font["name"]
        ok = True
        try:
            name_record = name.getName(nameID=6, platformID=1, platEncID=0)
            encoding = name_record.getEncoding("utf-8")
            s = name_record.string.decode(encoding)
            return s
        except Exception as e:
            #print(e)
            ok = False
        if not ok:
            try:
                name_record = name.getName(nameID=6, platformID=3, platEncID=1)
                encoding = name_record.getEncoding("utf-8")
                s = name_record.string.decode(encoding)
                return s
            except Exception as e:
                #print(e)
                ok = False
        return None

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

    def is_recent_file(self, file, always_recent=False):
        if always_recent:
            return True
        now = datetime.datetime.now()
        dt = datetime.datetime.fromtimestamp(os.stat(file).st_mtime)
        elapsed = (now - dt).total_seconds()
        return elapsed < 180

def get_args():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-d", "--dir", dest="basedir", default=None,
                        help="directory where web fonts are searched")
    args = parser.parse_args()

    return args

def main():
     args = get_args()
     basedirs = [args.basedir] if args.basedir is not None else None
     tool = WebfontAnalyzer(basedirs)
     sys.exit(tool.run())

if __name__ == "__main__":
    main()
