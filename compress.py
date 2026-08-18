#!/usr/bin/env python3

"""Script principal de compressão de arquivos."""

import argparse
import sys
from pathlib import Path

from compressor import Compressor
from utils import check_dependencies

# Importar módulos do Google Drive apenas quando necessário
process_drive_tree = None
DRIVE_AVAILABLE = False
try:
    from drive_processor import process_drive_tree
    DRIVE_AVAILABLE = True
except ImportError:
    pass


def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Compressor de vídeos, imagens e PDFs"
    )

    parser.add_argument(
        "--in-place",
        "-i",
        action="store_true",
        help="Substitui o arquivo original pelo comprimido",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mostra saída detalhada dos comandos",
    )

    parser.add_argument(
        "--drive",
        action="store_true",
        help="Processa arquivos do Google Drive",
    )

    parser.add_argument(
        "--drive-delete-revisions",
        action="store_true",
        help="Remove revisões antigas ao processar arquivos do Drive",
    )
    
    parser.add_argument(
        "--drive-folder-id",
        help="ID da pasta do Google Drive a processar",
    )

    parser.add_argument(
        "--drive-workers",
        type=int,
        default=None,
        help="Quantidade máxima de pastas processadas simultaneamente",
    )

    parser.add_argument("origem", nargs="?", help="Diretório de origem")

    parser.add_argument("destino", nargs="?", help="Diretório de destino")

    args = parser.parse_args()
    drive_workers = args.drive_workers if args.drive_workers is not None else 4

    # Validações de argumentos
    if args.drive:
        # --drive-folder-id é obrigatório quando --drive está ativo
        if not args.drive_folder_id:
            print("❌ --drive-folder-id é obrigatório quando --drive está ativo.")
            sys.exit(1)
        
        # --in-place não pode ser usado com --drive
        if args.in_place:
            print("❌ --in-place não pode ser usado em conjunto com --drive.")
            sys.exit(1)
        
        # Argumentos origem e destino não são usados no modo --drive
        if args.origem is not None or args.destino is not None:
            print("❌ No modo --drive, não especifique origem ou destino.")
            sys.exit(1)

        if drive_workers < 1:
            print("❌ --drive-workers deve ser maior ou igual a 1.")
            sys.exit(1)

        if not DRIVE_AVAILABLE or process_drive_tree is None:
            print("❌ Módulos do Google Drive não disponíveis.")
            print("Instale as dependências: pip install -r requirements.txt")
            sys.exit(1)

        check_dependencies()

        result = process_drive_tree(
            root_folder_id=args.drive_folder_id,
            delete_revisions=args.drive_delete_revisions,
            verbose=args.verbose,
            workers=drive_workers,
        )

        if result["failed"]:
            sys.exit(1)

        return
    
    # Validações para modo local (sem --drive)
    # --drive-folder-id e --drive-delete-revisions só podem ser usados no modo --drive
    if args.drive_folder_id:
        print("❌ --drive-folder-id só pode ser usado no modo --drive.")
        sys.exit(1)
    
    if args.drive_delete_revisions:
        print("❌ --drive-delete-revisions só pode ser usado no modo --drive.")
        sys.exit(1)

    if args.drive_workers is not None:
        print("❌ --drive-workers só pode ser usado no modo --drive.")
        sys.exit(1)
    
    # Validações para --in-place
    if args.in_place:
        # Se --in-place está ativo, origem é obrigatório e destino não pode ser especificado
        if not args.origem:
            print("❌ Origem é obrigatório quando --in-place está ativo.")
            sys.exit(1)
        if args.destino:
            print("❌ Quando --in-place está ativo, não especifique destino.")
            sys.exit(1)
    else:
        # Se --in-place não está ativo, origem e destino são obrigatórios
        if not args.origem:
            print("❌ Origem é obrigatório quando --in-place não está ativo.")
            sys.exit(1)
        if not args.destino:
            print("❌ Destino é obrigatório quando --in-place não está ativo.")
            sys.exit(1)

    check_dependencies()

    origem = Path(args.origem)

    if not origem.exists():
        print("❌ Diretório de origem inexistente.")
        sys.exit(1)

    if args.in_place:
        destino = origem
    else:
        destino = Path(args.destino)

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
