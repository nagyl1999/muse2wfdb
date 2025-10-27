"""
muse2wfdb.converter
-------------------
Convert GE MUSE XML ECG exports to WFDB (WaveForm Database) format.

Author: Levente Nagy
License: MIT
"""


import base64
import logging

from pathlib import Path
from typing import Dict, Any, Optional, List

import wfdb
import xmltodict
import numpy as np


logger = logging.getLogger(__name__)

# Standard 12-lead ECG names
LEAD_NAMES: List[str] = [
    'I', 'II', 'III', 'aVR', 'aVL', 'aVF',
    'V1', 'V2', 'V3', 'V4', 'V5', 'V6'
]

QRS_TYPE_MAP = {
    "0": "N",   # Normal
    "1": "V",   # Ventricular
    "2": "S",   # Supraventricular
}

UNIT_SCALE_MAP = {
    "MICROVOLTS": 0.001,  # µV → mV
    "MILLIVOLTS": 1.0,    # mV → mV
    "VOLTS": 1000.0       #  V → mV
}


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

    logger.info("Reading MUSE file: %s", path)
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


def process_waveforms(waveform: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """
    Decode base64 ECG waveforms for each lead and compute derived leads.

    Args:
        waveform: The selected waveform dictionary from the MUSE file.
    """
    lead_waveforms: Dict[str, np.ndarray] = {lead_name: [] for lead_name in LEAD_NAMES}

    lead_list = waveform["LeadData"]
    if isinstance(lead_list, dict):
        lead_list = [lead_list]

    for lead in lead_list:
        lead_id = lead["LeadID"].strip().upper()
        lead_data = lead["WaveFormData"]
        decoded = base64.b64decode(lead_data)
        samples = np.frombuffer(decoded, dtype="<i2")

        scale = UNIT_SCALE_MAP.get(lead["LeadAmplitudeUnits"].strip().upper())
        if scale is None:
            raise ValueError(f"Unknown amplitude unit: {lead['LeadAmplitudeUnits']}")

        # Convert to mV
        lead_waveforms[lead_id] = samples * float(lead["LeadAmplitudeUnitsPerBit"]) * scale
        logger.debug("Processed lead %s: %s samples.", lead_id, len(samples))

    # Compute derived leads
    if "I" in lead_waveforms and "II" in lead_waveforms:
        lead_waveforms["III"] = lead_waveforms["II"] - lead_waveforms["I"]
        lead_waveforms["aVR"] = -(lead_waveforms["I"] + lead_waveforms["II"]) / 2
        lead_waveforms["aVL"] = lead_waveforms["I"] - 0.5 * lead_waveforms["II"]
        lead_waveforms["aVF"] = lead_waveforms["II"] - 0.5 * lead_waveforms["I"]
        logger.debug("Derived leads (III, aVR, aVL, aVF) computed.")
    else:
        logger.warning("Cannot compute derived leads: leads I or II missing.")

    return lead_waveforms


def save_wfdb(lead_waveforms: Dict[str, np.ndarray], output_name: str = "wfdb_record",
              comments: Optional[List[str]] = None, fs: int = 500) -> None:
    """
    Save the processed ECG signals into WFDB format (.hea and .dat files).

    Args:
        lead_waveforms: The processed waveforms of the MUSE export.
        output_name: The base name for the output WFDB files.
        fs: Sampling frequency in Hz (default: 500).
    """
    comments = comments or []
    logger.info("Saving WFDB record '%s' at %s Hz", output_name, fs)

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
        p_signal=signals,
        fmt=['16'] * signals.shape[1],
        comments=comments
    )

    logger.info("WFDB files saved: %s.hea / %s.dat", output_name, output_name)


def save_qrs_annotations(record_name: str, qrs_data: list):
    """
    Save QRS annotations from parsed MUSE XML data to a WFDB .atr file.

    Parameters
    ----------
    record_name : str
        Name of the WFDB record (without extension)
    qrs_data : list[dict]
        List of QRS entries, each with keys ['Number', 'Type', 'Time']
    fs : int
        Sampling frequency (Hz)
    """
    logger.info("Saving QRS annotations for record '%s'", record_name)

    # Convert <Time> (ms) to sample index
    samples = np.array([int(qrs['Time']) for qrs in qrs_data])

    # Symbol: all 'N' (normal) by default; can map from 'Type'
    symbols = np.array([QRS_TYPE_MAP.get(qrs['Type'], 'N') for qrs in qrs_data])

    # Optional aux notes
    aux_notes = np.array([f"QRS_{qrs['Number']}" for qrs in qrs_data])

    wfdb.wrann(
        record_name=record_name,
        sample=samples,
        symbol=symbols,
        aux_note=aux_notes,
        extension='atr'
    )

    logger.debug("Saved %s QRS annotations.", len(samples))


def muse_to_wfdb(path: str, output_name: str = "wfdb_record",
                 comments: Optional[List[str]] = None) -> bool:
    """
    Main function to convert a MUSE XML ECG file into WFDB format.

    Args:
        path: Path to the input MUSE XML file.
        output_name: Output WFDB record name (without extension).

    Returns:
        Wether annotations were saved.
    """
    comments = comments or []
    logger.info("Converting MUSE XML to WFDB: %s", path)

    ecg_data = read_muse_file(path)
    waveform = select_waveform(ecg_data)

    # Process leads
    frequency = int(waveform.get("SampleBase", 500))
    lead_waveforms = process_waveforms(waveform)

    # Save processed data in WFDB format
    save_wfdb(lead_waveforms, output_name, comments, frequency)

    # Save complexes in WFDB format
    qrs_info = ecg_data["RestingECG"].get("QRSTimesTypes", {}).get("QRS")
    if qrs_info:
        save_qrs_annotations(output_name, qrs_info)
        return True

    logger.info("MUSE XML to WFDB conversion completed successfully.")
    return False
