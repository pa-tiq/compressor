#!/usr/bin/env python3

"""Funções utilitárias do compressor."""

import shutil
import subprocess
import sys
import signal


def signal_handler(sig, frame):
    """Handler para sinal Ctrl+C."""
    print("\n🛑 Script abortado pelo usuário (Ctrl+C)!")
    sys.exit(1)


signal.signal(signal.SIGINT, signal_handler)


def _nvenc_funciona(codec):
    """Tenta codificar um frame de teste para confirmar que a GPU/driver
    realmente suportam o encoder, e não apenas que o ffmpeg foi compilado
    com suporte a ele."""
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=256x256:d=1",
        "-c:v",
        codec,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]

    return subprocess.run(cmd, capture_output=True).returncode == 0


def detect_video_codec():
    """Detecta o codec de vídeo disponível no sistema.

    Prioriza a GPU NVIDIA (NVENC) quando disponível e funcional; caso
    contrário, cai para codificação por CPU (libx265/libx264).

    Retorna (codec, qualidade, preset, usa_gpu).
    """
    result = subprocess.run(
        ["ffmpeg", "-encoders"],
        capture_output=True,
        text=True,
    )

    encoders = result.stdout

    if shutil.which("nvidia-smi") is not None:
        for codec in ("hevc_nvenc", "h264_nvenc"):
            if codec in encoders and _nvenc_funciona(codec):
                print(f"🚀 GPU NVIDIA detectada. Usando {codec} (NVENC).")
                return codec, "32", "p5", True

        print(
            "⚠️ GPU NVIDIA encontrada, mas o NVENC não respondeu "
            "(driver/ffmpeg sem suporte). Usando CPU."
        )

    if "libx265" in encoders:
        return "libx265", "28", "medium", False

    print("⚠️ libx265 não encontrado. Usando H.264.")
    return "libx264", "23", "medium", False


def check_dependencies():
    """Verifica se as dependências do sistema estão instaladas."""
    dependencies = {
        "ffmpeg": "sudo apt install ffmpeg",
        "heif-convert": "sudo apt install libheif-examples",
        "gs": "sudo apt install ghostscript",
    }
    for command, install in dependencies.items():
        if shutil.which(command) is None:
            print(f"❌ {command} não encontrado.")
            print(f"Instale com: {install}")
            sys.exit(1)


def run_command(command, verbose):
    """Executa um comando e retorna True se bem-sucedido."""
    if verbose:
        return subprocess.run(command).returncode == 0

    return (
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )