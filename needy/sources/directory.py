import os
import shutil

from ..source import Source


class Directory(Source):
    def __init__(self, directory, directory_source):
        Source.__init__(self, directory)
        self.__directory_source = directory_source

    @classmethod
    def identifier(cls):
        return 'directory'

    def clean(self):
        if os.path.isdir(self.source_directory()):
            shutil.rmtree(self.source_directory())
        elif os.path.exists(self.source_directory()):
            os.remove(self.source_directory())
        shutil.copytree(self.__directory_source, self.source_directory(), symlinks=True, ignore=shutil.ignore_patterns('.*'))
