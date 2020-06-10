#!/usr/bin/env python3

from sfdata import SFDataFile


with SFDataFile("run_000041.BSREAD.h5") as data:
    print(data)
    print("#entries:", len(data))
#    print(data.names)

    ch = data["SLAAR11-LTIM01-EVR0:DUMMY_PV1_NBS"]
    print(ch)
    print(ch.pids)
    print(ch.data)

    subset = data["SLAAR11-LTIM01-EVR0:DUMMY_PV1_NBS", "SLAAR11-LTIM01-EVR0:DUMMY_PV2_NBS"]
    print(subset)

    df = subset.to_dataframe()
#    print(df)



