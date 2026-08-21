#!/usr/bin/env python3

"""Processamento paralelo de arquivos do Google Drive por pasta."""

from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing
from queue import Empty
import tempfile
from pathlib import Path

from compressor import Compressor
from config import DRIVE_MIME_TYPES, IMAGE_EXTENSIONS, PDF_EXTENSIONS, VIDEO_EXTENSIONS
from drive_client import GoogleDrive
from drive_logger import DriveLogger


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_progress_queue = None
_worker_id = "W?"
_progress = (0, 0)


def configure_progress(progress_queue):
    """Configura a fila de progresso compartilhada com o processo principal."""
    global _progress_queue, _worker_id
    _progress_queue = progress_queue
    process_name = multiprocessing.current_process().name
    _worker_id = f"W{process_name.rsplit('-', 1)[-1]}"


def folder_log(folder_label, message):
    """Imprime uma mensagem identificada pela pasta processada."""
    if _progress_queue is None:
        print(f"[PASTA: {folder_label}] {message}")
        return

    _progress_queue.put((_worker_id, folder_label, _progress, message))


def process_drive_folder(compressor, folder_id, delete_revisions=False, folder_label=None):
    """Processa exclusivamente os arquivos diretamente pertencentes a uma pasta."""
    drive = GoogleDrive()
    label = folder_label or folder_id
    logger = DriveLogger(output=lambda message: folder_log(label, message))
    files = list(drive.list_files(folder_id))
    supported = [
        file for file in files
        if file.get("mimeType") != FOLDER_MIME_TYPE
        and Path(file["name"]).suffix.lower()
        in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | PDF_EXTENSIONS)
    ]

    logger.start_session(folder_id, len(supported))
    files_with_app_properties = [
        file for file in supported
        if drive.has_app_property(file, "compressor_script")
    ]
    files_without_app_properties = [
        file for file in supported
        if not drive.has_app_property(file, "compressor_script")
    ]

    if files_with_app_properties:
        folder_log(label, f"{len(files_with_app_properties)} arquivo(s) já marcado(s) no Drive - pulado(s).")

    if delete_revisions and files_without_app_properties:
        folder_log(label, f"Deletando revisões antigas de {len(files_without_app_properties)} arquivo(s)...")
        deleted_total = sum(
            drive.delete_old_revisions(file["id"])
            for file in files_without_app_properties
        )
        folder_log(label, f"{deleted_total} revisão(ões) removida(s) no total.")

    remaining_files = logger.get_remaining_files(files_without_app_properties)
    truly_remaining = []
    app_properties_skipped = 0
    for file in remaining_files:
        if not drive.has_app_property(file, "compressor_script"):
            truly_remaining.append(file)
        else:
            logger.mark_file_skipped(file["id"], "Já comprimido pelo script (appProperties)")
            app_properties_skipped += 1

    logger_skipped_files = []
    for file in files_without_app_properties:
        file_id = file["id"]
        if logger.is_file_processed(file_id, file["name"]):
            if not drive.has_app_property(file, "compressor_script"):
                try:
                    drive.set_app_property(file_id, "compressor_script", "1")
                    logger_skipped_files.append(file["name"])
                except Exception as error:
                    folder_log(label, f"Não foi possível marcar {file['name']} no Drive: {error}")

    if app_properties_skipped:
        folder_log(label, f"{app_properties_skipped} arquivo(s) pulado(s) pelo appProperties do Drive.")
    if logger_skipped_files:
        folder_log(label, f"{len(logger_skipped_files)} arquivo(s) do logger marcado(s) com appProperties.")

    remaining_files = truly_remaining
    folder_log(label, f"Arquivos válidos: {len(supported)}; para processar: {len(remaining_files)}")

    for index, file in enumerate(remaining_files, start=1):
        global _progress
        _progress = (index, len(remaining_files))
        file_id = file["id"]
        name = file["name"]
        original_size = int(file.get("size", 0))
        ext = Path(name).suffix.lower()
        folder_log(label, f"[{index}/{len(remaining_files)}] Processando {name}")
        logger.mark_file_in_progress(file_id, name)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            source = temp_dir / name
            output = source.with_suffix(".jpg") if ext in {".png", ".heic", ".heif"} else source
            folder_log(label, f"Baixando {name}...")
            try:
                drive.download(file, source)
            except Exception as error:
                folder_log(label, f"Falha no download: {error}")
                logger.mark_file_failed(file_id, error)
                continue

            compressed = temp_dir / f"compressed{output.suffix}"
            folder_log(label, f"Comprimindo {name}...")
            if not compressor.compress_single(source, compressed):
                folder_log(label, "Falha na compressão.")
                logger.mark_file_failed(file_id, "Falha na compressão")
                continue

            compressed_size = compressed.stat().st_size
            folder_log(label, f"Original: {original_size / 1024 / 1024:.2f} MB; comprimido: {compressed_size / 1024 / 1024:.2f} MB")
            if compressed_size >= original_size:
                folder_log(label, "Arquivo comprimido não ficou menor; upload ignorado.")
                logger.mark_file_skipped(file_id, "Arquivo não ficou menor após compressão")
                try:
                    drive.set_app_property(file_id, "compressor_script", "1")
                except Exception as error:
                    folder_log(label, f"Não foi possível marcar arquivo como processado: {error}")
                continue

            reduction = (1 - compressed_size / original_size) * 100
            mime_type = DRIVE_MIME_TYPES.get(output.suffix.lower(), "application/octet-stream")
            folder_log(label, f"Enviando {name} para o Google Drive...")
            try:
                drive.update_file(
                    file_id=file_id,
                    local_path=compressed,
                    name=output.name,
                    mime_type=mime_type,
                    app_properties={"compressor_script": "1"},
                )
            except Exception as error:
                folder_log(label, f"Falha no upload: {error}")
                logger.mark_file_failed(file_id, error)
                continue

            folder_log(label, "Arquivo atualizado.")
            if delete_revisions:
                deleted = drive.delete_old_revisions(file_id)
                folder_log(label, f"{deleted} revisão(ões) removida(s).")
            logger.mark_file_completed(file_id, original_size, compressed_size, reduction)
            try:
                drive.set_app_property(file_id, "compressor_script", "1")
            except Exception as error:
                folder_log(label, f"Não foi possível marcar arquivo como processado: {error}")

    logger.complete_session()
    return {
        "folder_id": folder_id,
        "folder_name": label,
        "status": "completed",
        "supported": len(supported),
        "remaining": len(remaining_files),
        "empty": not supported,
    }


def process_drive_folder_worker(folder_info, delete_revisions, verbose):
    """Worker independente para processar uma pasta em seu próprio processo."""
    label = folder_info.get("path") or folder_info["name"]
    compressor = Compressor(
        Path("."),
        Path("."),
        in_place=False,
        verbose=verbose,
        status_callback=lambda message: folder_log(label, message),
    )
    return process_drive_folder(
        compressor,
        folder_id=folder_info["id"],
        delete_revisions=delete_revisions,
        folder_label=label,
    )


def process_drive_tree(root_folder_id, delete_revisions=False, verbose=False, workers=4):
    """Descobre a árvore e processa cada pasta com paralelismo limitado."""
    if workers < 1:
        raise ValueError("workers deve ser maior ou igual a 1")

    drive = GoogleDrive()
    folders = list(drive.list_folders_recursive(root_folder_id))
    print(f"📁 Pastas encontradas: {len(folders)}")
    completed = 0
    empty = 0
    failed = []

    with multiprocessing.Manager() as manager:
        progress_queue = manager.Queue()
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=configure_progress,
            initargs=(progress_queue,),
        ) as executor:
            futures = {
                executor.submit(process_drive_folder_worker, folder, delete_revisions, verbose): folder
                for folder in folders
            }
            active_futures = set(futures)
            statuses = {}
            rendered_lines = 0

            def render_progress():
                nonlocal rendered_lines
                changed = False
                while True:
                    try:
                        worker, label, progress, message = progress_queue.get_nowait()
                    except Empty:
                        break
                    current, total = progress
                    statuses[worker] = f"[{worker}] {label} [{current}/{total}] {message}"
                    changed = True

                if not changed:
                    return

                if rendered_lines:
                    print(f"\033[{rendered_lines}A", end="")
                for worker in sorted(statuses):
                    print(f"\033[2K{statuses[worker]}")
                rendered_lines = len(statuses)

            while active_futures:
                done, active_futures = wait(active_futures, timeout=0.2, return_when=FIRST_COMPLETED)
                render_progress()
                for future in done:
                    folder = futures[future]
                    try:
                        result = future.result()
                        completed += 1
                        empty += int(result.get("empty", False))
                    except Exception as error:
                        failed.append((folder.get("path") or folder["name"], error))
                        print(f"\033[2K❌ Falha na pasta {folder.get('path') or folder['name']}: {error}")

            render_progress()
            if rendered_lines:
                print()

    print("========================================")
    print("PROCESSAMENTO DO DRIVE CONCLUÍDO")
    print("========================================")
    print(f"Pastas encontradas: {len(folders)}")
    print(f"Pastas concluídas:  {completed}")
    print(f"Pastas sem arquivos: {empty}")
    print(f"Pastas com falha:   {len(failed)}")
    print(f"Workers utilizados: {workers}")
    print("========================================")
    return {"found": len(folders), "completed": completed, "failed": failed, "empty": empty}


def process_drive(compressor, folder_id, delete_revisions=False):
    """Mantém compatibilidade com chamadas antigas de uma única pasta."""
    return process_drive_folder(compressor, folder_id, delete_revisions)
