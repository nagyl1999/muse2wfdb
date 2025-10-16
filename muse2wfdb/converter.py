"""
muse2wfdb.converter
-------------------
Convert GE MUSE XML ECG exports to WFDB (WaveForm Database) format.

Author: Levente Nagy
License: MIT
"""

import wfdb
import array
import base64
import xmltodict
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List

# Standard 12-lead ECG names
LEAD_NAMES: List[str] = [
    'I', 'II', 'III', 'aVR', 'aVL', 'aVF',
    'V1', 'V2', 'V3', 'V4', 'V5', 'V6'
]

# Global dictionary to store waveform data per lead
lead_waveforms: Dict[str, np.ndarray] = {lead: np.array([]) for lead in LEAD_NAMES}


def read_muse_file(path: str) -> Dict[str, Any]:
    """
    Read and parse a GE MUSE XML file into a Python dictionary.

    Args:
        path: Path to the XML file exported from MUSE.

    Returns:
        Parsed XML structure as a Python dictionary.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"MUSE file not found: {path}")

    with open(path, "rb") as muse_file:
        return xmltodict.parse(muse_file.read().decode("utf-8"))


def select_waveform(ecg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select the 'Rhythm' waveform section from the MUSE ECG XML structure.

    Args:
        ecg: Parsed MUSE ECG dictionary.

    Returns:
        The waveform dictionary that corresponds to the 'Rhythm' ECG signal.
    """
    for waveform in ecg["RestingECG"]["Waveform"]:
        if waveform["WaveformType"] == "Rhythm":
            return waveform
    raise ValueError("No 'Rhythm' waveform found in MUSE ECG file.")


def process_waveforms(waveform: Dict[str, Any]) -> None:
    """
    Decode base64 ECG waveforms for each lead and compute derived leads.

    Args:
        waveform: The selected waveform dictionary from the MUSE file.
    """
    for lead in waveform["LeadData"]:
        lead_data = lead["WaveFormData"]
        decoded = base64.b64decode(lead_data)
        samples = np.array(array.array("h", decoded))
        lead_waveforms[lead["LeadID"]] = samples / 1000  # convert to mV

    # Compute derived leads
    lead_waveforms["III"] = lead_waveforms["II"] - lead_waveforms["I"]
    lead_waveforms["aVR"] = -(lead_waveforms["I"] + lead_waveforms["II"]) / 2
    lead_waveforms["aVL"] = lead_waveforms["I"] - 0.5 * lead_waveforms["II"]
    lead_waveforms["aVF"] = lead_waveforms["II"] - 0.5 * lead_waveforms["I"]


def save_wfdb(output_name: str = "example_record", fs: int = 500) -> None:
    """
    Save the processed ECG signals into WFDB format (.hea and .dat files).

    Args:
        output_name: The base name for the output WFDB files.
        fs: Sampling frequency in Hz (default: 500).
    """
    signals = []
    for lead in LEAD_NAMES:
        if lead_waveforms[lead].size == 0:
            raise ValueError(f"Missing waveform data for lead: {lead}")
        signals.append(lead_waveforms[lead])

    # Stack all leads into (N, 12) matrix
    signals = np.column_stack(signals)

    wfdb.wrsamp(
        record_name=output_name,
        fs=fs,
        units=["mV"] * len(LEAD_NAMES),
        sig_name=LEAD_NAMES,
        p_signal=signals
    )


def muse_to_wfdb(path: str, output_name: str = "example_record") -> None:
    """
    Main function to convert a MUSE XML ECG file into WFDB format.

    Args:
        path: Path to the input MUSE XML file.
        output_name: Output WFDB record name (without extension).
    """
    ecg = read_muse_file(path)
    waveform = select_waveform(ecg)
    process_waveforms(waveform)
    save_wfdb(output_name)
