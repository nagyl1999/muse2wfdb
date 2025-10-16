from muse2wfdb.converter import muse_to_wfdb
import wfdb

muse_export = "examples/anonim_pac_xml_export.txt"
wfdb_filename = "patient001_ecg"

muse_to_wfdb(muse_export, wfdb_filename)

record = wfdb.rdrecord(wfdb_filename)
annotation = wfdb.rdann(wfdb_filename, 'atr')

wfdb.plot_wfdb(record=record, annotation=annotation, title="MUSE exported ECG")