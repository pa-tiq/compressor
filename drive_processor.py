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
from drive_logger import DriveLogger


def process_drive(
    compressor,
    folder_id,
    delete_revisions=False,
):    
    """Processa arquivos do Google Drive."""
    drive = GoogleDrive()
    logger = DriveLogger()

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

    # Iniciar sessão de logging
    logger.start_session(folder_id, len(supported))
    
    # Filtrar apenas arquivos não processados
    remaining_files = logger.get_remaining_files(supported)
    
    # Verificar também appProperties para arquivos que não estão no logger
    truly_remaining = []
    app_properties_skipped = 0
    for file in remaining_files:
        if not drive.has_app_property(file, "compressor_script"):
            truly_remaining.append(file)
        else:
            # Se tem appProperties mas não está no logger, adicionar ao logger como skip
            file_id = file["id"]
            file_name = file["name"]
            logger.mark_file_skipped(file_id, "Já comprimido pelo script (appProperties)")
            app_properties_skipped += 1
    
    if app_properties_skipped > 0:
        print(f"📝 {app_properties_skipped} arquivo(s) pulado(s) pelo appProperties do Drive.")
    
    remaining_files = truly_remaining
    
    print()
    print(f"☁️ Arquivos encontrados: {len(supported)}")
    print(f"📝 Arquivos para processar: {len(remaining_files)}")
    print()

    for index, file in enumerate(remaining_files, start=1):

        file_id = file["id"]
        name = file["name"]
        original_size = int(file.get("size", 0))

        ext = Path(name).suffix.lower()

        # Verificar se o arquivo já foi comprimido pelo script usando appProperties
        if drive.has_app_property(file, "compressor_script"):
            print(
                f"[{index}/{len(remaining_files)}] "
                f"📄 {name}"
            )
            print("⏭️ Arquivo já marcado como comprimido pelo script (appProperties). Pulando.")
            logger.mark_file_skipped(file_id, "Já comprimido pelo script (appProperties)")
            continue

        print(
            f"[{index}/{len(remaining_files)}] "
            f"📄 {name}"
        )

        # Marcar arquivo como em processamento
        logger.mark_file_in_progress(file_id, name)

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
                    file,
                    source,
                )

            except Exception as e:

                print(f"❌ Falha no download: {e}")
                logger.mark_file_failed(file_id, e)
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
                logger.mark_file_failed(file_id, "Falha na compressão")
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
                logger.mark_file_skipped(file_id, "Arquivo não ficou menor após compressão")
                
                # Marcar arquivo como processado mesmo que não tenha ficado menor
                try:
                    drive.set_app_property(file_id, "compressor_script", "1")
                    print("✅ Arquivo marcado como processado (appProperties).")
                except Exception as e:
                    print(f"⚠️ Não foi possível marcar arquivo como processado: {e}")
                
                # Deletar revisões antigas mesmo se arquivo não ficou menor
                if delete_revisions:
                    print("🗑️ Removendo revisões antigas...")
                    deleted = drive.delete_old_revisions(file_id)
                    print(f"✅ {deleted} revisão(ões) removida(s).")
                
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
                    app_properties={"compressor_script": "1"},
                )

            except Exception as e:

                print(f"❌ Falha no upload: {e}")
                logger.mark_file_failed(file_id, e)
                continue

            print("✅ Arquivo atualizado.")

            # Marcar arquivo como concluído
            logger.mark_file_completed(file_id, original_size, compressed_size, reduction)

            if delete_revisions:

                print("🗑️ Removendo revisões antigas...")

                deleted = drive.delete_old_revisions(
                    file_id,
                )

                print(
                    f"✅ {deleted} revisão(ões) removida(s)."
                )

        print()
    
    # Marcar sessão como concluída
    logger.complete_session()
