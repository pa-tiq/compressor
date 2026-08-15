#!/usr/bin/env python3

import argparse
import shutil
import signal
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".flv",
    ".wmv",
    ".webm",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


# --------------------------------------------------------
# Ctrl+C
# --------------------------------------------------------
def signal_handler(sig, frame):
    print("\n🛑 Script abortado pelo usuário (Ctrl+C)!")
    sys.exit(1)


signal.signal(signal.SIGINT, signal_handler)


# --------------------------------------------------------
# Verifica ffmpeg
# --------------------------------------------------------
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        print("❌ ffmpeg não encontrado.")
        print("Instale com:")
        print("sudo apt install ffmpeg")
        sys.exit(1)


# --------------------------------------------------------
# Detecta encoder disponível
# --------------------------------------------------------
def detect_video_codec():

    result = subprocess.run(
        ["ffmpeg", "-encoders"],
        capture_output=True,
        text=True,
    )

    if "libx265" in result.stdout:
        return "libx265", "28", "medium"

    print("⚠️ libx265 não encontrado. Usando H.264.")
    return "libx264", "23", "medium"


# --------------------------------------------------------
# Executa ffmpeg
# --------------------------------------------------------
def run_ffmpeg(command, verbose):

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


# --------------------------------------------------------
# Processamento
# --------------------------------------------------------
class Compressor:

    def __init__(
        self,
        origem: Path,
        destino: Path,
        in_place: bool,
        verbose: bool,
    ):

        self.origem = origem.resolve()
        self.destino = destino.resolve()

        self.in_place = in_place
        self.verbose = verbose

        self.destino.mkdir(parents=True, exist_ok=True)

        self.log_file = self.destino / ".compress_progress.log"

        self.processados = set()

        if self.log_file.exists():
            self.processados = {
                linha.strip()
                for linha in self.log_file.read_text().splitlines()
                if linha.strip()
            }

        (
            self.video_codec,
            self.crf,
            self.preset,
        ) = detect_video_codec()

    def save_log(self, path: Path):

        with self.log_file.open("a") as f:
            f.write(str(path) + "\n")

        self.processados.add(str(path))

    def process(self):

        total = 0

        print("🔍 Procurando arquivos...")

        for arquivo in self.origem.rglob("*"):

            if not arquivo.is_file():
                continue

            ext = arquivo.suffix.lower()

            if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                continue

            if self.process_file(arquivo):
                total += 1

        print()
        print(f"✅ Concluído! {total} arquivos processados.")

        if self.in_place:
            print(f"📁 Arquivos substituídos em {self.origem}")
        else:
            print(f"📁 Cópia comprimida em {self.destino}")

    def process_file(self, src: Path):

        rel = src.relative_to(self.origem)

        dest = self.destino / rel

        ext = src.suffix.lower()

        if ext == ".png":
            dest = dest.with_suffix(".jpg")

        log_path = src if self.in_place else dest

        if str(log_path) in self.processados:
            print(f"⏭️ Já processado: {rel}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)

        if ext == ".png":
            return self.convert_png(src, dest)

        if self.in_place:
            return self.compress_in_place(src)

        return self.compress_copy(src, dest)

    def convert_png(self, src, dest):

        print(f"🖼️ Convertendo PNG -> JPG: {src.relative_to(self.origem)}")

        cmd = [
            "ffmpeg",
            "-i",
            str(src),
            "-q:v",
            "4",
            "-y",
            str(dest),
        ]

        ok = run_ffmpeg(cmd, self.verbose)

        if not ok:
            print(f"❌ Falha: {src}")
            return False

        if self.in_place:
            src.unlink()

        self.save_log(dest if not self.in_place else dest)

        print("✅ Convertido.")

        return True

    def compress_in_place(self, src):

        ext = src.suffix.lower()

        tmp = src.with_suffix(src.suffix + ".tmp" + ext)

        print(f"🎬 Comprimindo: {src.relative_to(self.origem)}")

        if ext in VIDEO_EXTENSIONS:

            cmd = [
                "ffmpeg",
                "-i",
                str(src),
                "-c:v",
                self.video_codec,
                "-crf",
                self.crf,
                "-preset",
                self.preset,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-y",
                str(tmp),
            ]

        else:

            cmd = [
                "ffmpeg",
                "-i",
                str(src),
                "-q:v",
                "4",
                "-y",
                str(tmp),
            ]

        ok = run_ffmpeg(cmd, self.verbose)

        if not ok or not tmp.exists():
            print(f"❌ Falha: {src}")
            return False

        tmp.replace(src)

        self.save_log(src)

        print("✅ Comprimido.")

        return True

    def compress_copy(self, src, dest):

        shutil.copy2(src, dest)

        ext = src.suffix.lower()

        tmp = dest.with_suffix(dest.suffix + ".tmp" + ext)

        print(f"🎬 Comprimindo: {src.relative_to(self.origem)}")

        if ext in VIDEO_EXTENSIONS:

            cmd = [
                "ffmpeg",
                "-i",
                str(dest),
                "-c:v",
                self.video_codec,
                "-crf",
                self.crf,
                "-preset",
                self.preset,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-y",
                str(tmp),
            ]

        else:

            cmd = [
                "ffmpeg",
                "-i",
                str(dest),
                "-q:v",
                "4",
                "-y",
                str(tmp),
            ]

        ok = run_ffmpeg(cmd, self.verbose)

        if not ok or not tmp.exists():
            print(f"❌ Falha: {src}")
            return False

        tmp.replace(dest)

        self.save_log(dest)

        print("✅ Comprimido.")

        return True


# --------------------------------------------------------
# Main
# --------------------------------------------------------
def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--in-place",
        "-i",
        action="store_true",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
    )

    parser.add_argument("origem")

    parser.add_argument("destino", nargs="?")

    args = parser.parse_args()

    check_ffmpeg()

    origem = Path(args.origem)

    if not origem.exists():
        print("❌ Diretório de origem inexistente.")
        sys.exit(1)

    if args.in_place:
        destino = origem
    else:
        destino = (
            Path(args.destino)
            if args.destino
            else Path.cwd() / origem.name
        )

    print(f"📂 Origem : {origem.resolve()}")
    print(f"📁 Destino: {destino.resolve()}")

    compressor = Compressor(
        origem,
        destino,
        args.in_place,
        args.verbose,
    )

    compressor.process()


if __name__ == "__main__":
    main()