#!/usr/bin/env python3

"""Processador de arquivos do Google Drive."""

import tempfile
from pathlib import Path

from config import (
    DRIVE_MIME_TYPES,
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from drive_client import GoogleDrive


def process_drive(
    compressor,
    folder_id,
    delete_revisions=False,
):    
    """Processa arquivos do Google Drive."""
    drive = GoogleDrive()

    files = list(
        drive.list_files(folder_id)
    )
    supported = []

    for file in files:

        name = file["name"]
        ext = Path(name).suffix.lower()

        if ext in VIDEO_EXTENSIONS:
            supported.append(file)

        elif ext in IMAGE_EXTENSIONS:
            supported.append(file)

        elif ext in PDF_EXTENSIONS:
            supported.append(file)

    print()
    print(f"☁️ Arquivos encontrados: {len(supported)}")
    print()

    for index, file in enumerate(supported, start=1):

        file_id = file["id"]
        name = file["name"]
        original_size = int(file.get("size", 0))

        ext = Path(name).suffix.lower()

        print(
            f"[{index}/{len(supported)}] "
            f"📄 {name}"
        )

        with tempfile.TemporaryDirectory() as temp_dir:

            temp_dir = Path(temp_dir)

            source = temp_dir / name

            # HEIC/HEIF/PNG viram JPG.
            if ext in {".png", ".heic", ".heif"}:
                output = source.with_suffix(".jpg")

            else:
                output = source

            print("⬇️ Baixando...")

            try:
                drive.download(
                    file_id,
                    source,
                )

            except Exception as e:

                print(f"❌ Falha no download: {e}")
                continue

            compressed = temp_dir / (
                f"compressed{output.suffix}"
            )

            if output == source:
                compressed = (
                    temp_dir
                    / f"compressed{source.suffix}"
                )

            print("🗜️ Comprimindo...")

            if not compressor.compress_single(
                source,
                compressed,
            ):
                print("❌ Falha na compressão.")
                continue

            compressed_size = compressed.stat().st_size

            print(
                f"   Original:    "
                f"{original_size / 1024 / 1024:.2f} MB"
            )

            print(
                f"   Comprimido:  "
                f"{compressed_size / 1024 / 1024:.2f} MB"
            )

            if compressed_size >= original_size:

                print(
                    "⏭️ Arquivo comprimido não ficou menor. "
                    "Upload ignorado."
                )

                continue

            reduction = (
                1 - compressed_size / original_size
            ) * 100

            print(
                f"   Redução:     {reduction:.1f}%"
            )

            new_name = output.name

            mime_type = (
                DRIVE_MIME_TYPES.get(
                    output.suffix.lower(),
                    "application/octet-stream",
                )
            )

            print("⬆️ Enviando para o Google Drive...")

            try:

                drive.update_file(
                    file_id=file_id,
                    local_path=compressed,
                    name=new_name,
                    mime_type=mime_type,
                )

            except Exception as e:

                print(f"❌ Falha no upload: {e}")
                continue

            print("✅ Arquivo atualizado.")

            if delete_revisions:

                print("🗑️ Removendo revisões antigas...")

                deleted = drive.delete_old_revisions(
                    file_id,
                )

                print(
                    f"✅ {deleted} revisão(ões) removida(s)."
                )

        print()
