"""Hardware capability detector — decides whether to enable LLM based on system specs.

Rules:
  - If VRAM >= 12 GB on any GPU → LLM capable (GPU inference)
  - Else if RAM >= 32 GB         → LLM capable (CPU inference, slower)
  - Otherwise                    → heuristic-only mode

Works cross-platform (Windows, Linux, macOS).  Zero required dependencies
beyond the standard library; nvidia-smi / subprocess are used opportunistically.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Thresholds (in GB)
MIN_VRAM_GB = 12.0
MIN_RAM_GB = 32.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class HardwareInfo:
    """Immutable snapshot of detected hardware."""

    __slots__ = ("ram_gb", "gpus", "os_name", "llm_capable", "reason")

    def __init__(
        self,
        ram_gb: float,
        gpus: list[dict],
        os_name: str,
        llm_capable: bool,
        reason: str,
    ):
        self.ram_gb = ram_gb
        self.gpus = gpus
        self.os_name = os_name
        self.llm_capable = llm_capable
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "ram_gb": round(self.ram_gb, 1),
            "gpus": self.gpus,
            "os_name": self.os_name,
            "llm_capable": self.llm_capable,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"HardwareInfo(ram={self.ram_gb:.1f}GB, "
            f"gpus={len(self.gpus)}, llm_capable={self.llm_capable}, "
            f"reason={self.reason!r})"
        )


def detect_hardware() -> HardwareInfo:
    """Detect RAM and GPU VRAM, then decide if LLM inference is viable."""
    os_name = platform.system()
    ram_gb = _detect_ram_gb()
    gpus = _detect_gpus()

    max_vram = max((g["vram_gb"] for g in gpus), default=0.0)

    if max_vram >= MIN_VRAM_GB:
        capable = True
        reason = f"GPU detected with {max_vram:.1f} GB VRAM (>= {MIN_VRAM_GB} GB)"
    elif ram_gb >= MIN_RAM_GB:
        capable = True
        reason = f"System RAM {ram_gb:.1f} GB (>= {MIN_RAM_GB} GB) — CPU inference"
    else:
        capable = False
        reason = (
            f"VRAM {max_vram:.1f} GB < {MIN_VRAM_GB} GB and "
            f"RAM {ram_gb:.1f} GB < {MIN_RAM_GB} GB — heuristic-only mode"
        )

    info = HardwareInfo(
        ram_gb=ram_gb,
        gpus=gpus,
        os_name=os_name,
        llm_capable=capable,
        reason=reason,
    )
    logger.info("Hardware detection: %s", info)
    return info


# ---------------------------------------------------------------------------
# RAM detection
# ---------------------------------------------------------------------------
def _detect_ram_gb() -> float:
    """Return total physical RAM in GB (best-effort)."""
    # Try psutil first (most reliable if installed)
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass

    system = platform.system()

    # Try Windows first (also works under MSYS/Git Bash/Cygwin on Windows)
    if system == "Windows" or "NT" in system or os.name == "nt":
        result = _ram_windows()
        if result > 0:
            return result

    if system == "Linux":
        result = _ram_linux()
        if result > 0:
            return result

    if system == "Darwin":
        result = _ram_macos()
        if result > 0:
            return result

    # Last resort: try all methods
    for fn in (_ram_windows, _ram_linux, _ram_macos):
        result = fn()
        if result > 0:
            return result

    return 0.0


def _ram_windows() -> float:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullTotalPhys / (1024 ** 3)
    except Exception:
        return 0.0


def _ram_linux() -> float:
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / (1024 ** 2)
    except Exception:
        pass
    return 0.0


def _ram_macos() -> float:
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
        return int(out.strip()) / (1024 ** 3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# GPU / VRAM detection
# ---------------------------------------------------------------------------
def _detect_gpus() -> list[dict]:
    """Return a list of {name, vram_gb} dicts for detected GPUs."""
    gpus: list[dict] = []

    # 1. Try nvidia-smi (NVIDIA GPUs)
    gpus.extend(_nvidia_smi_gpus())

    # 2. Try AMD ROCm (Linux)
    if not gpus:
        gpus.extend(_amd_rocm_gpus())

    return gpus


def _nvidia_smi_gpus() -> list[dict]:
    """Query nvidia-smi for GPU names and VRAM (MiB)."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return []

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        gpus: list[dict] = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                name = parts[0]
                try:
                    vram_mib = float(parts[1])
                    vram_gb = vram_mib / 1024.0
                except ValueError:
                    vram_gb = 0.0
                gpus.append({"name": name, "vram_gb": round(vram_gb, 1)})
        return gpus
    except Exception as e:
        logger.debug("nvidia-smi failed: %s", e)
        return []


def _amd_rocm_gpus() -> list[dict]:
    """Query rocm-smi for AMD GPUs (Linux only)."""
    rocm_smi = shutil.which("rocm-smi")
    if not rocm_smi:
        return []

    try:
        result = subprocess.run(
            [rocm_smi, "--showmeminfo", "vram", "--csv"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        gpus: list[dict] = []
        for line in result.stdout.strip().splitlines()[1:]:  # skip header
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    vram_bytes = int(parts[1])
                    vram_gb = vram_bytes / (1024 ** 3)
                    gpus.append({
                        "name": f"AMD GPU {len(gpus)}",
                        "vram_gb": round(vram_gb, 1),
                    })
                except ValueError:
                    continue
        return gpus
    except Exception as e:
        logger.debug("rocm-smi failed: %s", e)
        return []
