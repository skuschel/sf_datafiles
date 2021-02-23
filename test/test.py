#!/usr/bin/env python3

# coverage run --source sfdata -m unittest discover && coverage report -m

#TODO:
# add test for unique pids handling


import os
import sys

this_dir = os.path.dirname(__file__)
sys.path.insert(0, (os.path.join(this_dir, "..")))


import io
import unittest
import unittest.mock
import numpy as np

from utils import TestCase, identity, make_temp_filename, read_names, load_df_from_csv, SettingWithCopyError

from sfdata import SFDataFiles, SFDataFile
from sfdata.errors import NoMatchingFileError, NoUsableFileError
from sfdata.closedh5 import ClosedH5Error
from sfdata.filecontext import FileContext
from sfdata.utils import typename, h5_boolean_indexing, json_load, strlen, maxstrlen, print_line, cprint, dip, percentage_missing, decide_color, apply_batched, batched
from sfdata.utils.progress import bar, percentage # not actually used anywhere
from sfdata.utils.np import nothing_like


FNAME_SCALARS = "fake_data/run_test.SCALARS.h5"
FNAME_ARRAYS  = "fake_data/run_test.ARRAYS.h5"
FNAME_ALL     = "fake_data/run_test.*.h5"
FNAME_DF      = "fake_data/example_df.csv"

CH_1D_NAME      = "ch1"
CH_1D_COL_NAME  = "ch2"
CH_ND_NAME      = "ch5"

CH_NAMES = ["ch1", "ch2", "ch3", "ch4", "ch5", "ch6"]

ANY_PIDS = [0, 2]
ALL_PIDS = [0, 1, 2]

CH_1D_PIDS      = [0, 1, 2]
CH_1D_DATA      = [0.1, 2.3, 4.5]
CH_1D_COL_DATA  = [6.7, 8.9, 0.1]
CH_ND_DATA1     = [[8.9, 0.1, 2.3], [4.5, 6.7, 8.9], [0.1, 2.3, 4.5]]

CH_ND_SHAPE = (3, 3, 3)

REPR_FILES   = 'SFDataFiles("fake_data/run_test.ARRAYS.h5", "fake_data/run_test.SCALARS.h5"): 6 channels'
REPR_FILE    = 'SFDataFile("fake_data/run_test.SCALARS.h5"): 3 channels'
REPR_SUBSET  = 'SFData: 6 channels'
REPR_CHANNEL = 'SFChannel: ch5'


PRINT_STATE_COMPLETE_FALSE = """
--------------------------------------------------------------------------------

\x1b[31mch3 2 / 3 -> 33% loss ▇▇▇▇▇▇\x1b[39m
\x1b[31mch6 2 / 3 -> 33% loss ▇▇▇▇▇▇\x1b[39m

\x1b[31mover the whole data set: 2 / 3 -> 33% loss\x1b[39m
\x1b[31mcomplete channels: 4 / 6 -> 33% incomplete\x1b[39m
\x1b[32mcomplete channels are hidden\x1b[39m

--------------------------------------------------------------------------------

"""


PRINT_STATE_COMPLETE_TRUE = """
--------------------------------------------------------------------------------

\x1b[32mch1 3 / 3 ->  0% loss ▇▇▇▇▇▇▇▇▇▇\x1b[39m
\x1b[32mch2 3 / 3 ->  0% loss ▇▇▇▇▇▇▇▇▇▇\x1b[39m
\x1b[31mch3 2 / 3 -> 33% loss ▇▇▇▇▇▇\x1b[39m
\x1b[32mch4 3 / 3 ->  0% loss ▇▇▇▇▇▇▇▇▇▇\x1b[39m
\x1b[32mch5 3 / 3 ->  0% loss ▇▇▇▇▇▇▇▇▇▇\x1b[39m
\x1b[31mch6 2 / 3 -> 33% loss ▇▇▇▇▇▇\x1b[39m

\x1b[31mover the whole data set: 2 / 3 -> 33% loss\x1b[39m
\x1b[31mcomplete channels: 4 / 6 -> 33% incomplete\x1b[39m

--------------------------------------------------------------------------------

"""



def check_channel_closed(testcase, ch):
    with testcase.assertRaises(ClosedH5Error):
        ch.data
    with testcase.assertRaises(ClosedH5Error):
        ch.pids

    with testcase.assertRaises(ClosedH5Error):
        ch.shape
    with testcase.assertRaises(ClosedH5Error):
        ch.dtype
    with testcase.assertRaises(ClosedH5Error):
        ch.ndim
    with testcase.assertRaises(ClosedH5Error):
        ch.size



class TestSFDataFiles(TestCase):

    def run(self, *args, **kwargs):
        with SFDataFiles(FNAME_ALL) as data:
            self.data = data
            super().run(*args, **kwargs)

    def test_subset_across_files(self):
        subset = self.data[CH_1D_NAME, CH_ND_NAME]
        self.assertAllEqual(
            subset[CH_1D_NAME].data, CH_1D_DATA
        )
        self.assertAllEqual(
            subset[CH_ND_NAME].data[1], CH_ND_DATA1
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.data), REPR_FILES
        )

    def test_error(self):
        with self.assertRaises(NoMatchingFileError):
            SFDataFiles("does not exist")
        broken_file = "fake_data/run_broken.SCALARS.h5"
        msg = f"Warning: Skipping \"{broken_file}\" since it caused OSError: Unable to open file (file signature not found)"
        with self.assertRaises(NoMatchingFileError), self.assertPrints(msg):
            SFDataFiles(broken_file)


    def test_closed1(self):
        with SFDataFiles(FNAME_ALL) as data:
            ch = data[CH_1D_NAME]
        check_channel_closed(self, ch)

    def test_closed2(self):
        data = SFDataFiles(FNAME_ALL)
        ch = data[CH_1D_NAME]
        data.close()
        check_channel_closed(self, ch)

    def test_closed_twice(self):
        data = SFDataFiles(FNAME_ALL)
        ch = data[CH_1D_NAME]
        data.close()
        data.close()
        check_channel_closed(self, ch)

    def test_closed_wrong(self):
        data = SFDataFiles(FNAME_ALL)
        ch = data[CH_1D_NAME]
        for f in data.files:
            f.file.close() # close only h5 file
            f.close()      # also create ClosedH5, which cannot read file info
        check_channel_closed(self, ch)



class TestSFDataFile(TestCase):

    def run(self, *args, **kwargs):
        with SFDataFile(FNAME_SCALARS) as data:
            self.data = data
            super().run(*args, **kwargs)

    def test_subset(self):
        subset = self.data[CH_1D_NAME, CH_1D_COL_NAME]
        self.assertAllEqual(
            subset[CH_1D_NAME].data, CH_1D_DATA
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.data), REPR_FILE
        )


    def test_closed1(self):
        with SFDataFile(FNAME_SCALARS) as data:
            ch = data[CH_1D_NAME]
        check_channel_closed(self, ch)

    def test_closed2(self):
        data = SFDataFile(FNAME_SCALARS)
        ch = data[CH_1D_NAME]
        data.close()
        check_channel_closed(self, ch)

    def test_closed_twice(self):
        data = SFDataFile(FNAME_SCALARS)
        ch = data[CH_1D_NAME]
        data.close()
        data.close()
        check_channel_closed(self, ch)

    def test_closed_wrong(self):
        data = SFDataFile(FNAME_SCALARS)
        ch = data[CH_1D_NAME]
        data.file.close() # close only h5 file
        data.close()      # also create ClosedH5, which cannot read file info
        check_channel_closed(self, ch)

    def test_spurios_pids(self):
        with SFDataFile("fake_data/run_spurious_pids.ARRAYS.h5") as data:
            self.assertTrue("pulse_id" not in data)



class TestSFData(TestCase):

    def run(self, *args, **kwargs):
        with SFDataFiles(FNAME_ALL) as data:
            self.data = data[data.names] # subset with all names to convert to plain SFData
            super().run(*args, **kwargs)

    def test_read_one_channel_data(self):
        self.assertAllEqual(
            self.data[CH_1D_NAME].data, CH_1D_DATA
        )

    def test_read_one_channel_pids(self):
        self.assertAllEqual(
            self.data[CH_1D_NAME].pids, CH_1D_PIDS
        )

    def test_pids(self):
        self.assertAllEqual(
            self.data.pids, ANY_PIDS
        )

    def test_all_pids(self):
        self.assertAllEqual(
            self.data.all_pids, ALL_PIDS
        )

    def test_name(self):
        self.assertEqual(
            sorted(self.data.names), CH_NAMES
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.data), REPR_SUBSET
        )

    def test_names_file_vs_files(self):
        with SFDataFile(FNAME_SCALARS) as data1, SFDataFiles(FNAME_SCALARS) as data2:
            self.assertEqual(
                data1.names, data2.names
            )

    def test_print_stats(self):
        with self.assertStdout(PRINT_STATE_COMPLETE_FALSE):
            self.data.print_stats(show_complete=False)
        with self.assertStdout(PRINT_STATE_COMPLETE_TRUE):
            self.data.print_stats(show_complete=True)



class TestSFChannel(TestCase):

    df_ref = load_df_from_csv(FNAME_DF)


    def run(self, *args, **kwargs):
        with SFDataFiles(FNAME_ALL) as data:
            self.data = data
            self.ch = data[CH_ND_NAME]
            super().run(*args, **kwargs)

    def test_read_one_channel_data(self):
        self.assertAllEqual(
            self.data[CH_1D_NAME].data, CH_1D_DATA
        )

    def test_read_one_channel_pids(self):
        self.assertAllEqual(
            self.data[CH_1D_NAME].pids, CH_1D_PIDS
        )

    def test_reset_valid(self):
        self.ch.valid = None
        self.ch.reset_valid()
        self.assertEqual(
            self.ch.valid, Ellipsis
        )

    def test_datasets_pids(self):
        self.assertEqual(
            self.ch.datasets.pids.shape, self.ch.pids.shape
        )
        self.assertEqual(
            self.ch.datasets.data.shape, self.ch.data.shape
        )

    def test_shape_all_valid(self):
        self.assertEqual(
            self.ch.shape, CH_ND_SHAPE
        )

    def test_shape_partial_valid(self):
        replacement_valid = [0, 1]
        new_shape = list(CH_ND_SHAPE)
        new_shape[0] = len(replacement_valid)
        new_shape = tuple(new_shape)
        self.ch.valid = replacement_valid
        self.assertEqual(
            self.ch.shape, new_shape
        )
        self.ch.reset_valid()

    def test_name(self):
        self.assertEqual(
            self.ch.name, CH_ND_NAME
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.ch), REPR_CHANNEL
        )

    def test_dataframe_setting(self):
        data = self.data
        methods = (data.to_dataframe, data.to_dataframe_accumulate, data.to_dataframe_fill)
        for func in methods:
            with self.assertNotRaises(SettingWithCopyError):
                func()


    @unittest.mock.patch("sfdata.sfdata.tqdm", identity)
    def test_to_dataframe(self):
        df_ref = self.df_ref
        data = self.data
        methods = (data.to_dataframe, data.to_dataframe_accumulate, data.to_dataframe_fill)
        for func in methods:
            for progress in (True, False):
                df = func(show_progress=progress)
                df.fillna(np.nan, inplace=True) #TODO: object array messes with df.equals below

                self.assertEqual(
                    df.shape, df_ref.shape
                )
                self.assertAllEqual(
                    df.columns, df_ref.columns
                )
                self.assertAllEqual(
                    df.index, df_ref.index
                )
                self.assertTrue(
                    df.equals(df_ref)
                )


    @unittest.mock.patch("sfdata.sfdata.tqdm", identity)
    def test_to_xarray(self):
        #TODO: reference only works for 1D arrays
        xr_ref = self.df_ref[["ch1", "ch2", "ch3"]].to_xarray().rename(index = "pids")
        data = self.data["ch1", "ch2", "ch3"]
        methods = (data.to_xarray, data.to_xarray_accumulate)
        for func in methods:
            for progress in (True, False):
                xr = func(show_progress=progress)

                self.assertEqual(
                    xr.sizes, xr_ref.sizes
                )
                self.assertEqual(
                    xr.dims, xr_ref.dims
                )
                self.assertAllEqual(
                    xr.coords, xr_ref.coords
                )
                self.assertAllEqual(
                    xr.indexes, xr_ref.indexes
                )
                self.assertTrue(
                    xr.equals(xr_ref)
                )


    def test_drop_missing(self):
        self.data.drop_missing()
        self.assertAllEqual(
            self.ch.valid, [0, 2]
        )
        self.data.reset_valid()
        self.assertEqual(
            self.ch.valid, Ellipsis
        )

    @unittest.mock.patch("sfdata.sfdata.tqdm", identity)
    def test_drop_missing_progressbar(self):
        self.data.drop_missing(show_progress=True)
        self.assertAllEqual(
            self.ch.valid, [0, 2]
        )
        self.data.reset_valid()
        self.assertEqual(
            self.ch.valid, Ellipsis
        )

    def test_save_names(self):
        with self.assertNotRaises():
            self.data.save_names("/dev/null", "w")

    def test_save_names_write_w(self):
        with self.assertNotRaises():
            fname = make_temp_filename(text=True)
            self.data.save_names(fname, "w")
            os.remove(fname)

    def test_save_names_write_x(self):
        with self.assertNotRaises():
            fname = make_temp_filename(text=True)
            os.remove(fname)
            self.data.save_names(fname, "x")
            os.remove(fname)

    def test_save_names_write_x_fail(self):
        fname = make_temp_filename(text=True)
        with self.assertRaises(FileExistsError):
            self.data.save_names(fname, "x")
        os.remove(fname)

    def test_save_names_write_r_exists_fail(self):
        fname = make_temp_filename(text=True)
        with self.assertRaises(io.UnsupportedOperation):
            self.data.save_names(fname, "r")
        os.remove(fname)

    def test_save_names_write_r_not_exists_fail(self):
        fname = make_temp_filename(text=True)
        os.remove(fname)
        with self.assertRaises(FileNotFoundError):
            self.data.save_names(fname, "r")

    def test_save_names_readback(self):
        fname = make_temp_filename(text=True)
        self.data.save_names(fname, "w")
        names = set(self.data.names)
        rb = read_names(fname)
        self.assertEqual(
            names, rb
        )
        os.remove(fname)

    def test_get_item_with_wrong_key_type(self):
        with self.assertRaises(KeyError):
            self.data[1]

    def test_get_item_with_missing_key(self):
        with self.assertRaises(KeyError):
            self.data["notakey"]

    def test_read_column_vector(self):
        with SFDataFiles(FNAME_SCALARS) as data:
            self.assertAllEqual(
                data[CH_1D_COL_NAME].data, CH_1D_COL_DATA
            )


    def test_in_batches(self):
        for i in range(4):
            for j in range(4):
                n = i + 1
                m = j + 1

                res = []
                for index, batch in self.data[CH_1D_NAME].in_batches(n, m):
                    res.extend(batch)
                self.assertAllEqual(
                    res, CH_1D_DATA[:n*m]
                )


    def test_apply_in_batches(self):
        nop = lambda x: x
        for i in range(4):
            for j in range(4):
                n = i + 1
                m = j + 1

                res = self.data[CH_1D_NAME].apply_in_batches(nop, n, m)
                self.assertAllEqual(
                    res, CH_1D_DATA[:n*m]
                )



class TestFileContext(TestCase):

    def test_filecontext_init(self):
        """
        FileContext cannot be instantiated
        """
        with self.assertRaises(TypeError):
            FileContext()

    @unittest.mock.patch.multiple(FileContext, __abstractmethods__=set())
    def test_filecontext_close(self):
        """
        FileContext.close is an abstractmethod and not implemented
        """
        fc = FileContext()
        with self.assertRaises(NotImplementedError):
            fc.close()



class TestErrors(TestCase):

    def test_NoMatchingFileError(self):
        with self.assertRaises(NoMatchingFileError):
            raise NoMatchingFileError("some pattern")

    def test_NoUsableFileError(self):
        with self.assertRaises(NoUsableFileError):
            raise NoUsableFileError



class TestUtils(TestCase):

    def test_typename(self):
        class SomeClass: pass
        some_object = SomeClass()
        self.assertEqual(
            typename(some_object), "SomeClass"
        )

    def test_h5_boolean_indexing_1d(self):
        """
        For 1D boolean indexing into hdf5 is possible, 
        so compare function result with straight forward applying the index
        """
        with SFDataFile(FNAME_SCALARS) as data:
            ch = data["ch1"]
            pids = ch.pids
            bool_indices = (pids == 1)
            ds = ch.datasets.data
            self.assertEqual(
                h5_boolean_indexing(ds, bool_indices), ds[bool_indices]
            )

    def test_h5_boolean_indexing_nd(self):
        """
        For nD boolean indexing into hdf5 is not possible,
        so compare function result to hard-coded values
        """
        with SFDataFile(FNAME_ARRAYS) as data:
            ch = data["ch5"]
            pids = ch.pids
            bool_indices = (pids == 1)
            ds = ch.datasets.data
            self.assertAllEqual(
                h5_boolean_indexing(ds, bool_indices), [CH_ND_DATA1]
            )


    def test_np_nothing_like(self):
        for dtype in (float, int):
            ref = np.empty(0, dtype=dtype)
            arr = np.ones((2, 2), dtype=dtype)
            nl = nothing_like(arr)
            self.assertAllEqual(
                nl, ref
            )


    def test_json_load(self):
        ref = {
            "test int": 1,
            "test float": 1.23,
            "test dict": {
                "element": "test"
            },
            "test none": None
        }
        data = json_load("fake_data/test.json")
        self.assertEqual(data, ref)


    def test_strlen(self):
        self.assertEqual(strlen("test"), 4)

    def test_maxstrlen(self):
        strings = ("test", "tes", "te", "t")
        self.assertEqual(maxstrlen(strings), 4)

    def test_print_line(self):
        with self.assertStdout("\n" + 80 * "-" + "\n\n"):
            print_line()
        with self.assertStdout("\nxxx\n\n"):
            print_line(3, "x")


    def test_cprint(self):
        with self.assertStdout("\x1b[32mtest\x1b[39m\n"):
            cprint("test", color="green")
        with self.assertStdout("\x1b[31mtest\x1b[39m\n"):
            cprint("test", color="red")
        with self.assertRaises(ValueError):
            cprint("test", color="not a color")


    def test_progress_dip(self):
        block = "▇"
        res = dip(0)
        self.assertEqual(res, block * 10)
        res = dip(10)
        self.assertEqual(res, block * 9)
        res = dip(100)
        self.assertEqual(res, "")
        res = dip(50, block="x", n_blocks_total=2)
        self.assertEqual(res, "x")

    def test_progress_bar(self):
        block = "▇"
        res = bar(0)
        self.assertEqual(res, "")
        res = bar(10)
        self.assertEqual(res, block)
        res = bar(100)
        self.assertEqual(res, block * 10)
        res = bar(50, block="x", n_blocks_total=2)
        self.assertEqual(res, "x")

    def test_progress_decide_color(self):
        nmin, nmax = -1, 1
        c = decide_color(-1, nmin, nmax)
        self.assertEqual(c, "red")
        c = decide_color( 0, nmin, nmax)
        self.assertEqual(c, None)
        c = decide_color(+1, nmin, nmax)
        self.assertEqual(c, "green")

    def test_progress_percentage_missing(self):
        ntotal = 1000
        pm = percentage_missing(ntotal, ntotal)
        self.assertEqual(pm, 0)
        pm = percentage_missing(0, ntotal)
        self.assertEqual(pm, 100)
        pm = percentage_missing(333, ntotal, decimals=0)
        self.assertEqual(pm, 67)
        pm = percentage_missing(333, ntotal, decimals=1)
        self.assertEqual(pm, 66.7)
        pm = percentage_missing(333, ntotal, decimals=2)
        self.assertEqual(pm, 66.7)

    def test_progress_percentage(self):
        ntotal = 1000
        pm = percentage(ntotal, ntotal)
        self.assertEqual(pm, 100)
        pm = percentage(0, ntotal)
        self.assertEqual(pm, 0)
        pm = percentage(333, ntotal, decimals=0)
        self.assertEqual(pm, 33)
        pm = percentage(333, ntotal, decimals=1)
        self.assertEqual(pm, 33.3)
        pm = percentage(333, ntotal, decimals=2)
        self.assertEqual(pm, 33.3)


    def test_apply_batched(self):
        arr = np.arange(3)
        nop = lambda x: x

        res = apply_batched(nop, arr, arr, 0)
        self.assertAllEqual(res, [])

        res = apply_batched(nop, arr, arr, 1, nbatches=0)
        self.assertAllEqual(res, [])

        for i in range(4):
            for j in range(4):
                n = i + 1
                m = j + 1

                res = apply_batched(nop, arr, arr, m) # result is independent of batch size
                self.assertAllEqual(res, arr)

                res = apply_batched(nop, arr, arr, 1, nbatches=n)
                self.assertAllEqual(res, arr[:n])

                res = apply_batched(nop, arr, arr, 1, nbatches=100) # asking for too many batches
                self.assertAllEqual(res, arr)

                res = apply_batched(nop, arr, arr, m, nbatches=n)
                self.assertAllEqual(res, arr[:m*n])


    def test_batched(self):
        arr = np.arange(3)

        res = list(batched(arr, arr, 0)) # batch size zero -> nothing
        self.assertEqual(res, [])

        res = list(batched(arr, arr, 1, nbatches=0)) # number of batches zero -> nothing
        self.assertEqual(res, [])

        def compare(left, right):
            self.assertEqual(len(left), len(right))
            for l, r in zip(left, right):
                lind, larr = l
                rind, rarr = r
                self.assertEqual(lind, rind)
                self.assertAllEqual(larr, rarr)

        refs = [
            [ # n = 1
                (slice(0, 1), [0]),
                (slice(1, 2), [1]),
                (slice(2, 3), [2])
            ], [ # n = 2
                (slice(0, 2), [0, 1]),
                (slice(2, 4), [2])
            ], [ # n = 3
                (slice(0, 3), [0, 1, 2])
            ], [ # n = 4 (same as 3)
                (slice(0, 3), [0, 1, 2])
            ]
        ]

        for i, ref in enumerate(refs):
            n = i + 1
            res = list(batched(arr, arr, n))
            compare(res, ref)
            res = list(batched(arr, arr, n, nbatches=100)) # asking for too many batches
            compare(res, ref)
            res = list(batched(arr, arr, n, nbatches=1)) # asking only for first batch
            compare(res, ref[:1])





if __name__ == '__main__':
    unittest.main()



