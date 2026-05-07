from collections.abc import Sequence


class ReadOnlyList(Sequence):
    def __init__(self, data):
        self._data = data

    def __getitem__(self, index):
        return self._data[index]

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"ReadOnlyList({self._data!r})"
