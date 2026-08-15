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


def detect_video_codec():
    """Detecta o codec de vídeo disponível no sistema."""
    result = subprocess.run(
        ["ffmpeg", "-encoders"],
        capture_output=True,
        text=True,
    )

    if "libx265" in result.stdout:
        return "libx265", "28", "medium"

    print("⚠️ libx265 não encontrado. Usando H.264.")
    return "libx264", "23", "medium"


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
