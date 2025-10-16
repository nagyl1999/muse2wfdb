from muse2wfdb.converter import muse_to_wfdb
import wfdb

muse_export = "test_pat_xml_export.txt"
wfdb_filename = "patient001_ecg"

muse_to_wfdb(muse_export, wfdb_filename)

record = wfdb.rdrecord(wfdb_filename)
wfdb.plot_wfdb(record=record, title="MUSE exported ECG")