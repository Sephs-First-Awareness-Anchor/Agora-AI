"""Offline, restart-safe acoustic enrollment of two spoken names.

Samples MUST originate from actual PCM. No ASR string or synthetic filename
is accepted as a voice sample. Raw recording bytes are kept in memory only
long enough to extract bounded features; by default they are never persisted.
"""
from __future__ import annotations
from pathlib import Path
import json
import math
import os
import statistics
import tempfile
from typing import Mapping
import numpy as np

FEATURES = ("spectral_brightness","stress_position","rhythm_variation",
            "voicing","contour")
FEATURE_VERSION = "acoustic-pcm-v1"
SAMPLE_RATE = 16000
MIN_DURATION = .28
MIN_RMS = .012
MAX_RMS = .95
MIN_SIGNAL_FRACTION = .15


def extract_audio_features(pcm: bytes, sample_rate: int = SAMPLE_RATE):
    """Analyze genuine signed little-endian 16-bit mono PCM.

    Returns relative prosodic and spectral descriptors, not speech-to-text,
    proven phoneme labels, or a biometric identity claim.
    """
    if not isinstance(pcm,(bytes,bytearray)) or not pcm or len(pcm)%2:
        raise ValueError("A recorded PCM16 signal is required")
    if sample_rate not in (8000,16000,22050,44100,48000):
        raise ValueError("Unsupported PCM sample rate")
    data=np.frombuffer(pcm,dtype="<i2").astype(np.float64)/32768.
    if data.size < int(MIN_DURATION*sample_rate):
        raise ValueError("Recording too short")
    data=data-np.mean(data)
    rms=float(np.sqrt(np.mean(data*data)))
    if not (MIN_RMS <= rms < MAX_RMS):
        raise ValueError("Recording is silent, clipped or unusable")
    framesize=max(128,int(.030*sample_rate))
    hop=max(64,int(.015*sample_rate))
    energies=[]; bright=[]; voiced=[]; pitches=[]
    for pos in range(0,len(data)-framesize+1,hop):
        frame=data[pos:pos+framesize]
        energy=float(np.sqrt(np.mean(frame*frame)))
        energies.append(energy)
        fft=np.abs(np.fft.rfft(frame*np.hanning(len(frame))))+1e-12
        freqs=np.fft.rfftfreq(len(frame),1/sample_rate)
        bright.append(float(np.sum(fft[freqs>1700])/np.sum(fft)))
        if energy < rms*.23:
            voiced.append(0.)
            continue
        crossings=float(np.mean(np.abs(np.diff(np.signbit(frame))))) if frame.size>1 else 0.
        voiced.append(float(max(0.,1.-crossings*4.)))
        # Pitch contour uses autocorrelation only when a voiced period exists.
        windowed=frame*np.hanning(frame.size)
        corr=np.correlate(windowed,windowed,"full")[framesize-1:]
        low=int(sample_rate/360)
        high=min(int(sample_rate/75),len(corr)-1)
        if high>low and corr[low:high].size and corr[low+int(np.argmax(corr[low:high]))] >= corr[0]*.3:
            delay=low+int(np.argmax(corr[low:high]))
            pitches.append(sample_rate/delay)
    if not energies:
        raise ValueError("No usable speech frames")
    e=np.asarray(energies)
    mask=e>max(MIN_RMS*.5,float(np.max(e))*.2)
    if float(np.mean(mask))<MIN_SIGNAL_FRACTION:
        raise ValueError("Speech activity could not be isolated")
    peak=int(np.argmax(e))
    stress=peak/max(1,len(e)-1)
    # Temporal contrast represents syllable envelope variation, not word length.
    rhythm=float(np.std(e)/(np.mean(e)+1e-8))
    contour=.5
    if len(pitches)>=6:
        third=max(1,len(pitches)//3)
        median_start=statistics.median(pitches[:third])
        median_end=statistics.median(pitches[-third:])
        contour=max(0.,min(1.,.5+(median_end-median_start)/220.))
    return {
        "source":"pcm",
        "feature_version":FEATURE_VERSION,
        "sample_rate":int(sample_rate),
        "duration_ms":round(len(data)/sample_rate*1000),
        "spectral_brightness":round(float(np.median(bright)),4),
        "stress_position":round(stress,4),
        "rhythm_variation":round(float(max(0.,min(1.,rhythm))),4),
        "voicing":round(float(np.mean(np.asarray(voiced)[mask])),4),
        "contour":round(contour,4),
        "rms":round(rms,5),
    }


def _write_atomic(path:Path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(payload,f,indent=2,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _median(rows,key):
    return statistics.median(float(r[key]) for r in rows)


def pronunciation_consensus(rows):
    if len(rows)<3:
        raise ValueError("Three audio observations of this name are required")
    output={name:round(_median(rows,name),4) for name in FEATURES}
    deltas=[]
    for row in rows:
        deltas.append(sum(abs(float(row[k])-output[k]) for k in FEATURES)/len(FEATURES))
    # One anomalous recording reduces confidence, not an extra personality vote.
    med=statistics.median(deltas)
    output["confidence"]=round(max(.0,min(1.,1.-med*2.0)),3)
    output["count"]=len(rows)
    output["source"]="pcm"
    output["feature_version"]=FEATURE_VERSION
    return output


def _speaker_embedding(rows):
    # Provisional spectral/prosodic reference only, not authentication.
    return [round(_median(rows,k),4) for k in
            ("spectral_brightness","voicing","contour","rhythm_variation")]


def compare_speaker(sample: Mapping, speaker_records: Mapping[str,list],
                    accept_threshold=.12, abstain_threshold=.20):
    """Conservative tri-state matching; no name-text evidence is used."""
    v=[float(sample[k]) for k in ("spectral_brightness","voicing","contour","rhythm_variation")]
    distances=[]
    for person, centroid in speaker_records.items():
        if len(centroid)!=len(v):
            continue
        dist=math.sqrt(sum((a-b)**2 for a,b in zip(v,centroid))/len(v))
        distances.append((dist,person))
    if not distances:
        return ("unknown",0.)
    distance,name=min(distances)
    if distance>abstain_threshold:
        return ("unknown",0.)
    if distance>accept_threshold or (len(distances)>1 and
            sorted(distances)[1][0]-distance < .055):
        return ("unknown",max(.0,1.-distance))
    return (name,max(.0,1.-distance))


class EnrollmentSession:
    """Single owner for all six incremental captures and recovery."""
    def __init__(self,storage_path,identity=None):
        self.path=Path(storage_path)
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding="utf-8"))
            if identity and any(self.data["identity"].get(k)!=identity.get(k)
                for k in ("ai_name","user_name","mode","color","dob")):
                raise ValueError("Pending enrollment belongs to a different onboarding")
        else:
            if not identity:
                raise ValueError("Enrollment identity is required")
            if identity.get("mode") not in ("introvert","extrovert"):
                raise ValueError("A valid AI behavior mode is required")
            if not identity.get("ai_name") or not identity.get("user_name"):
                raise ValueError("Both typed names are required")
            self.data={"state":"PENDING_ENROLLMENT", "identity":identity,
                       "samples":{"user_name":[],"ai_name":[]},
                       "birth_account":None}
            _write_atomic(self.path,self.data)

    def add_pcm(self, target, pcm, sample_rate=SAMPLE_RATE):
        if target not in ("user_name","ai_name"):
            raise ValueError("Unknown enrollment target")
        if self.data["state"]!="PENDING_ENROLLMENT":
            raise ValueError("Enrollment is already complete")
        samples=self.data["samples"][target]
        if len(samples)>=3:
            raise ValueError("Three recordings already present")
        feature=extract_audio_features(pcm,sample_rate)
        samples.append(feature)
        _write_atomic(self.path,self.data)
        return feature

    def next_target(self):
        for target in ("user_name","ai_name"):
            if len(self.data["samples"][target])<3:
                return target
        return None

    def ready(self):
        return self.next_target() is None

    def result(self):
        if not self.ready():
            raise ValueError("All six PCM samples are mandatory")
        return {
            "ai_pronunciation":pronunciation_consensus(self.data["samples"]["ai_name"]),
            "user_pronunciation":pronunciation_consensus(self.data["samples"]["user_name"]),
            "provisional_speaker":{
                "source":"six-name-pcm",
                "confidence":"provisional-only",
                "embedding":_speaker_embedding(
                    self.data["samples"]["user_name"]+self.data["samples"]["ai_name"]),
                "not_authorization":True,
            },
        }

    def stage_account(self,account_id,serial_code):
        """Checkpoint the account reference before the immutable birth write."""
        previous=self.data.get("birth_account")
        if previous and previous["id"]!=account_id:
            raise ValueError("Account identity already staged")
        self.data["birth_account"]={"id":account_id,"serial_code":serial_code}
        _write_atomic(self.path,self.data)

    def mark_committed(self,account_id,serial_code):
        if not self.ready():
            raise ValueError("Cannot commit before recordings")
        if self.data.get("birth_account") and self.data["birth_account"]["id"]!=account_id:
            raise ValueError("Birth account already committed for another account")
        self.data["birth_account"]={"id":account_id,"serial_code":serial_code}
        self.data["state"]="BIRTH_COMMITTED"
        _write_atomic(self.path,self.data)


class NameLearningStore:
    """Mutable local pronunciation and speaker evidence, separate from birth.

    No voice recognition is used as authentication. New observations must
    arrive from PCM, never from a transcript or time-derived pseudofingerprint.
    """
    def __init__(self, account_dir):
        self.path=Path(account_dir)/"voice_learning.json"
        if self.path.exists():
            self.data=json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data=None

    def seed_once(self, identity, enrollment_result):
        if self.data is not None:
            return self.data
        self.data={
            "feature_version":FEATURE_VERSION,
            "names":{
                "user_name":{"typed":identity["user_name"],
                             "pronunciation":enrollment_result["user_pronunciation"]},
                "ai_name":{"typed":identity["ai_name"],
                           "pronunciation":enrollment_result["ai_pronunciation"]},
            },
            "speakers":{
                "owner":{"embedding":enrollment_result["provisional_speaker"]["embedding"],
                         "samples":6, "status":"provisional"}
            },
            "raw_recordings_saved":False,
            "recognition_is_authorization":False,
        }
        _write_atomic(self.path,self.data)
        return self.data

    def observe_pronunciation_pcm(self, target, pcm, sample_rate=SAMPLE_RATE):
        """Update how names are pronounced without touching immutable birth."""
        if self.data is None or target not in self.data["names"]:
            raise ValueError("Pronunciation learning is not initialized")
        feature=extract_audio_features(pcm,sample_rate)
        old=self.data["names"][target]["pronunciation"]
        for k in FEATURES:
            old[k]=round(.8*old[k]+.2*feature[k],4)
        old["observations_after_birth"]=old.get("observations_after_birth",0)+1
        _write_atomic(self.path,self.data)
        return old

    def classify_speaker_pcm(self, pcm, sample_rate=SAMPLE_RATE):
        if self.data is None:
            return ("unknown",0.)
        features=extract_audio_features(pcm,sample_rate)
        centroids={k:v["embedding"] for k,v in self.data["speakers"].items()}
        result, confidence=compare_speaker(features,centroids)
        if result=="unknown":
            return ("unknown",confidence)
        status=self.data["speakers"][result].get("status","provisional")
        if status!="validated":
            return ("provisional_"+result,confidence)
        return ("recognized_"+result,confidence)

    def add_consented_other_speaker(self, label, pcm_samples):
        """Explicit consenting enrollment; never learn unknown bystanders."""
        if self.data is None or not label or label=="owner":
            raise ValueError("Invalid known-speaker enrollment")
        if len(pcm_samples)<6:
            raise ValueError("Six consented utterances are needed for a provisional voice")
        rows=[extract_audio_features(pcm) for pcm in pcm_samples]
        self.data["speakers"][label]={
            "embedding":_speaker_embedding(rows),
            "samples":len(rows),"status":"provisional",
        }
        _write_atomic(self.path,self.data)

    def delete_voice_data(self):
        """Erase mutable features without changing immutable birth identity."""
        self.path.unlink(missing_ok=True)
        self.data=None
