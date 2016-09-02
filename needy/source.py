try:
    from exceptions import NotImplementedError
except ImportError:
    pass


class Source:
    def __init__(self, source_directory):
        self.__source_directory = source_directory

    @classmethod
    def identifier(cls):
        raise NotImplementedError('identifier')

    def clean(self):
        """ should fetch (if necessary) and clean the source """
        raise NotImplementedError('clean')

    def synchronize(self):
        """ should fetch (if necessary) while preserving local modifications """
        raise NotImplementedError('synchronize')

    def source_directory(self):
        return self.__source_directory

    def status(self):
        """ A human-readable string representing the status of the source """
        return self.identifier()
