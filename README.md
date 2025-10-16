# muse2wfdb
### Convert GE MUSE XML ECG exports to WFDB format

`muse2wfdb` is a lightweight Python library that converts ECG data exported from the GE MUSE Resting ECG System (in XML format) into WFDB (WaveForm DataBase) format, compatible with PhysioNet tools and the wfdb Python package.

## Installation

Install directly from PyPI:

```bash
pip install muse2wfdb
```

Or install locally from source:

```bash
git clone https://github.com/nagyl1999/muse2wfdb.git
cd muse2wfdb
pip install .
```

## Usage

An example is provided in the `examples` folder.

```python
from muse2wfdb.converter import muse_to_wfdb
import wfdb

muse_export = "test_pat_xml_export.txt"
wfdb_filename = "patient001_ecg"

muse_to_wfdb(muse_export, wfdb_filename)

record = wfdb.rdrecord(wfdb_filename)
wfdb.plot_wfdb(record=record, title="MUSE exported ECG")
```
