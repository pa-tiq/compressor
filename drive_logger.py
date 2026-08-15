#!/usr/bin/env python3

"""Sistema de logging para compressão de arquivos do Drive."""

import json
import os
from datetime import datetime
from pathlib import Path


class DriveLogger:
    """Gerencia logs de compressão do Drive para permitir retomar processamento."""

    def __init__(self, log_dir=".drive_logs"):
        """Inicializa o logger de Drive."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_log = None
        self.current_folder_id = None

    def get_log_file(self, folder_id):
        """Retorna o caminho do arquivo de log para uma pasta específica."""
        return self.log_dir / f"drive_{folder_id}.json"

    def load_log(self, folder_id):
        """Carrega o log de uma pasta específica."""
        log_file = self.get_log_file(folder_id)
        
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Criar novo log
        return {
            "folder_id": folder_id,
            "started_at": None,
            "last_updated": None,
            "completed_at": None,
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "skipped_files": 0,
            "files": {}
        }

    def save_log(self, log_data):
        """Salva o log de uma pasta específica."""
        log_file = self.get_log_file(log_data["folder_id"])
        
        log_data["last_updated"] = datetime.now().isoformat()
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    def start_session(self, folder_id, total_files):
        """Inicia uma nova sessão de compressão ou retoma uma existente."""
        self.current_folder_id = folder_id
        self.current_log = self.load_log(folder_id)
        
        # Se for uma nova sessão (nunca iniciada), criar do zero
        if self.current_log["started_at"] is None:
            self.current_log["started_at"] = datetime.now().isoformat()
            self.current_log["completed_at"] = None
            self.current_log["total_files"] = total_files
            self.current_log["processed_files"] = 0
            self.current_log["failed_files"] = 0
            self.current_log["skipped_files"] = 0
            self.current_log["files"] = {}
            print(f"📝 Iniciando nova sessão de compressão para pasta {folder_id}")
        else:
            # Retomar sessão existente (mesmo que tenha sido concluída)
            # Atualizar total de arquivos se mudou
            self.current_log["total_files"] = total_files
            # Marcar como não concluído para permitir reprocessamento de arquivos não processados
            self.current_log["completed_at"] = None
            
            print(f"📝 Retomando sessão para pasta {folder_id}")
            print(f"   Arquivos já processados: {self.current_log['processed_files']}")
            print(f"   Arquivos já pulados: {self.current_log['skipped_files']}")
            print(f"   Arquivos com falha: {self.current_log['failed_files']}")
        
        self.save_log(self.current_log)

    def is_file_processed(self, file_id, file_name):
        """Verifica se um arquivo já foi processado (com sucesso ou pulado)."""
        if not self.current_log:
            return False
        
        file_info = self.current_log["files"].get(file_id)
        if file_info and file_info.get("status") in ["completed", "skipped"]:
            return True
        
        return False

    def mark_file_in_progress(self, file_id, file_name):
        """Marca um arquivo como em processamento."""
        if not self.current_log:
            return
        
        self.current_log["files"][file_id] = {
            "name": file_name,
            "status": "in_progress",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None
        }
        self.save_log(self.current_log)

    def mark_file_completed(self, file_id, original_size, compressed_size, reduction):
        """Marca um arquivo como concluído com sucesso."""
        if not self.current_log:
            return
        
        # Incrementar contador apenas se não estava marcado como completed antes
        was_completed = False
        if file_id in self.current_log["files"]:
            if self.current_log["files"][file_id].get("status") == "completed":
                was_completed = True
            
            self.current_log["files"][file_id]["status"] = "completed"
            self.current_log["files"][file_id]["completed_at"] = datetime.now().isoformat()
            self.current_log["files"][file_id]["original_size"] = original_size
            self.current_log["files"][file_id]["compressed_size"] = compressed_size
            self.current_log["files"][file_id]["reduction"] = reduction
        else:
            self.current_log["files"][file_id] = {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "original_size": original_size,
                "compressed_size": compressed_size,
                "reduction": reduction
            }
        
        if not was_completed:
            self.current_log["processed_files"] += 1
        self.save_log(self.current_log)

    def mark_file_failed(self, file_id, error):
        """Marca um arquivo como falhou."""
        if not self.current_log:
            return
        
        if file_id in self.current_log["files"]:
            self.current_log["files"][file_id]["status"] = "failed"
            self.current_log["files"][file_id]["completed_at"] = datetime.now().isoformat()
            self.current_log["files"][file_id]["error"] = str(error)
            
            self.current_log["failed_files"] += 1
            self.save_log(self.current_log)

    def mark_file_skipped(self, file_id, reason):
        """Marca um arquivo como pulado."""
        if not self.current_log:
            return
        
        # Incrementar contador apenas se não estava marcado como skipped antes
        was_skipped = False
        if file_id in self.current_log["files"]:
            if self.current_log["files"][file_id].get("status") == "skipped":
                was_skipped = True
            
            self.current_log["files"][file_id]["status"] = "skipped"
            self.current_log["files"][file_id]["completed_at"] = datetime.now().isoformat()
            self.current_log["files"][file_id]["reason"] = reason
        else:
            self.current_log["files"][file_id] = {
                "status": "skipped",
                "completed_at": datetime.now().isoformat(),
                "reason": reason
            }
        
        if not was_skipped:
            self.current_log["skipped_files"] += 1
        self.save_log(self.current_log)

    def complete_session(self):
        """Marca a sessão como concluída."""
        if not self.current_log:
            return
        
        self.current_log["completed_at"] = datetime.now().isoformat()
        self.save_log(self.current_log)
        
        print(f"📝 Sessão concluída para pasta {self.current_folder_id}")
        print(f"   Total de arquivos: {self.current_log['total_files']}")
        print(f"   Processados com sucesso: {self.current_log['processed_files']}")
        print(f"   Falhas: {self.current_log['failed_files']}")
        print(f"   Pulados: {self.current_log['skipped_files']}")

    def get_remaining_files(self, files):
        """Retorna lista de arquivos que ainda não foram processados."""
        if not self.current_log:
            return files
        
        remaining = []
        for file in files:
            file_id = file["id"]
            if not self.is_file_processed(file_id, file["name"]):
                remaining.append(file)
        
        return remaining