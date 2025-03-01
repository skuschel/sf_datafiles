from collections.abc import Sequence
from .errors import NoMatchingFileError, NoUsableFileError
from .utils import typename, enquote, adjust_shape, json_load, print_skip_warning, FileStatus
from .sfdatafiles import SFDataFiles
from .ign import remove_ignored_filetypes_scan


class SFScanInfo(Sequence):

    def __init__(self, fname):
        self.fname = fname
        self.fs = FileStatus(fname)
        self.info = info = json_load(fname)

        self.files      = info["scan_files"]
        self.parameters = info["scan_parameters"]

        values    = info["scan_values"]
        readbacks = info["scan_readbacks"]

        self.values    = adjust_shape(values)
        self.readbacks = adjust_shape(readbacks)


    def __iter__(self):
#        return (SFDataFiles(*fns) for fns in self.files) #TODO: errors stop the iteration. do we want this?
        return generate_sfdata(self.files)

    def __getitem__(self, index):
        fns = self.files[index]
        if isinstance(index, slice):
            return generate_sfdata(fns)
        return SFDataFiles(*fns)

    def __len__(self):
        return len(self.files)


    def __repr__(self):
        tn = typename(self)
        fn = enquote(self.fname)
        nsteps = len(self)
        return f"{tn}({fn}): {nsteps} steps"



def generate_sfdata(fnames):
    fnames = remove_ignored_filetypes_scan(fnames)
    nothing_opened = True
    for i, fns in enumerate(fnames):
        try:
            with SFDataFiles(*fns) as data: #TODO: is this what we want? does it even work? maybe explict .close() after yield is better?
                yield data
            nothing_opened = False
        except Exception as exc:
            sn = f"step {i} {fns}"
            print_skip_warning(exc, sn)
    if nothing_opened:
        raise NoUsableFileError



