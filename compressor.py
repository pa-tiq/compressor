#!/usr/bin/env python3

"""Classe principal de compressão de arquivos."""

import shutil
from pathlib import Path

from config import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from utils import detect_video_codec, run_command


class Compressor:
    """Compressor de vídeos, imagens e PDFs."""

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
            self.gpu,
        ) = detect_video_codec()

    def _video_quality_args(self):
        """Argumentos de qualidade/preset do ffmpeg, adaptados ao encoder.

        NVENC (GPU) não aceita -crf: usa -rc vbr + -cq. O preset também
        usa a nomenclatura p1 (mais rápido) a p7 (melhor qualidade) em
        vez de ultrafast..veryslow usados pelos encoders de CPU.
        """
        if self.gpu:
            return [
                "-rc:v",
                "vbr",
                "-cq",
                self.crf,
                "-preset",
                self.preset,
            ]

        return [
            "-crf",
            self.crf,
            "-preset",
            self.preset,
        ]

    def compress_single(self, src: Path, dest: Path):
        """Comprime um único arquivo."""
        ext = src.suffix.lower()

        if ext in {".png", ".heic", ".heif"}:

            if ext in {".heic", ".heif"}:
                cmd = [
                    "heif-convert",
                    str(src),
                    str(dest),
                ]

            else:
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(src),
                    "-q:v",
                    "4",
                    "-y",
                    str(dest),
                ]

        elif ext in PDF_EXTENSIONS:

            cmd = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/ebook",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={dest}",
                str(src),
            ]

        elif ext in VIDEO_EXTENSIONS:

            cmd = [
                "ffmpeg",
                "-i",
                str(src),
                "-c:v",
                self.video_codec,
                *self._video_quality_args(),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-y",
                str(dest),
            ]

        else:

            # JPEG/JPG
            cmd = [
                "ffmpeg",
                "-i",
                str(src),
                "-q:v",
                "4",
                "-y",
                str(dest),
            ]

        return run_command(
            cmd,
            self.verbose,
        ) and dest.exists()

    def save_log(self, path: Path):
        """Salva o progresso no arquivo de log."""
        with self.log_file.open("a") as f:
            f.write(str(path) + "\n")

        self.processados.add(str(path))

    def process(self):
        """Processa todos os arquivos do diretório de origem."""
        total = 0

        print("🔍 Procurando arquivos...")

        for arquivo in self.origem.rglob("*"):

            if not arquivo.is_file():
                continue

            ext = arquivo.suffix.lower()

            if (
                ext not in VIDEO_EXTENSIONS
                and ext not in IMAGE_EXTENSIONS
                and ext not in PDF_EXTENSIONS
            ):
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
        """Processa um arquivo individual."""
        rel = src.relative_to(self.origem)

        dest = self.destino / rel

        ext = src.suffix.lower()

        if ext in {".png", ".heic", ".heif"}:
            dest = dest.with_suffix(".jpg")

        log_path = src if self.in_place else dest

        if str(log_path) in self.processados:
            print(f"⏭️ Já processado: {rel}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)

        if ext in {".png", ".heic", ".heif"}:
            return self.convert_image(src, dest)

        if ext in PDF_EXTENSIONS:
            return self.compress_pdf(src, dest)

        if self.in_place:
            return self.compress_in_place(src)

        return self.compress_copy(src, dest)

    def compress_pdf(self, src, dest):
        """Comprime um arquivo PDF."""
        print(f"📄 Comprimindo PDF: {src.relative_to(self.origem)}")

        tmp = dest.with_suffix(".tmp.pdf")

        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={tmp}",
            str(src),
        ]

        ok = run_command(cmd, self.verbose)

        if not ok or not tmp.exists():
            print(f"❌ Falha: {src}")
            tmp.unlink(missing_ok=True)
            return False

        tmp.replace(dest)

        self.save_log(dest)

        print("✅ PDF comprimido.")

        return True

    def convert_image(self, src, dest):
        """Converte imagens (PNG, HEIC, HEIF) para JPG."""
        print(
            f"🖼️ Convertendo {src.suffix.upper()} -> JPG: "
            f"{src.relative_to(self.origem)}"
        )

        if src.suffix.lower() in {".heic", ".heif"}:
            cmd = [
                "heif-convert",
                str(src),
                str(dest),
            ]
        else:
            cmd = [
                "ffmpeg",
                "-i",
                str(src),
                "-q:v",
                "4",
                "-y",
                str(dest),
            ]

        ok = run_command(cmd, self.verbose)

        if not ok or not dest.exists():
            print(f"❌ Falha: {src}")
            return False

        if self.in_place:
            src.unlink()

        self.save_log(dest)

        print("✅ Convertido.")

        return True

    def compress_in_place(self, src):
        """Comprime arquivo substituindo o original."""
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
                *self._video_quality_args(),
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

        ok = run_command(cmd, self.verbose)

        if not ok or not tmp.exists():
            print(f"❌ Falha: {src}")
            return False

        tmp.replace(src)

        self.save_log(src)

        print("✅ Comprimido.")

        return True

    def compress_copy(self, src, dest):
        """Comprime arquivo criando uma cópia."""
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
                *self._video_quality_args(),
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

        ok = run_command(cmd, self.verbose)

        if not ok or not tmp.exists():
            print(f"❌ Falha: {src}")
            return False

        tmp.replace(dest)

        self.save_log(dest)

        print("✅ Comprimido.")

        return True