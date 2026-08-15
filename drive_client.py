#!/usr/bin/env python3

"""Cliente Google Drive para autenticação e operações de arquivo."""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from config import DRIVE_SCOPES


def authenticate_drive():
    """Autentica com o Google Drive e retorna o serviço."""
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json",
            DRIVE_SCOPES,
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                DRIVE_SCOPES,
            )

            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build(
        "drive",
        "v3",
        credentials=creds,
    )


class GoogleDrive:
    """Cliente para operações no Google Drive."""

    def __init__(self):
        self.service = authenticate_drive()

    def list_files(self, folder_id=None):
        """Lista arquivos de uma pasta do Drive."""

        page_token = None

        query = "trashed = false"

        if folder_id:
            query += f" and '{folder_id}' in parents"

        while True:

            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    corpora="user",
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields=(
                        "nextPageToken,"
                        "files(id,name,mimeType,size,resourceKey,appProperties)"
                    ),
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )

            for file in response.get("files", []):
                yield file

            page_token = response.get("nextPageToken")

            if not page_token:
                break

    def download(self, file, destination):
        """Baixa um arquivo do Drive."""

        file_id = file["id"]
        resource_key = file.get("resourceKey")

        # Construir a URL de download diretamente
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=True"
        
        # Criar o request HTTP
        headers = {}
        if resource_key:
            headers["X-Goog-Drive-Resource-Keys"] = f"{file_id}/{resource_key}"
        
        # Usar o http object do serviço para fazer o request
        response, content = self.service._http.request(
            uri=url,
            method="GET",
            headers=headers
        )
        
        if response.status != 200:
            raise Exception(f"Erro no download: {response.status} - {content.decode('utf-8')}")
        
        with open(destination, "wb") as f:
            f.write(content)
        
        print("☁️ Download: 100.0%")

    def update_file(
        self,
        file_id,
        local_path,
        name,
        mime_type,
        app_properties=None,
    ):
        """Atualiza um arquivo no Drive."""
        media = MediaFileUpload(
            str(local_path),
            mimetype=mime_type,
            resumable=True,
        )

        metadata = {
            "name": name,
        }
        
        if app_properties:
            metadata["appProperties"] = app_properties

        return (
            self.service.files()
            .update(
                fileId=file_id,
                body=metadata,
                media_body=media,
                supportsAllDrives=True,
                fields="id,name,size",
            )
            .execute()
        )
    
    def set_app_property(self, file_id, key, value):
        """Define uma propriedade de aplicação em um arquivo."""
        # Primeiro obter as propriedades existentes
        file = self.service.files().get(
            fileId=file_id,
            fields="appProperties",
            supportsAllDrives=True
        ).execute()
        
        existing_properties = file.get("appProperties", {})
        existing_properties[key] = value
        
        # Atualizar apenas as propriedades (sem o conteúdo do arquivo)
        self.service.files().update(
            fileId=file_id,
            body={"appProperties": existing_properties},
            supportsAllDrives=True,
            fields="id"
        ).execute()
    
    def has_app_property(self, file, key):
        """Verifica se um arquivo tem uma propriedade de aplicação específica."""
        app_properties = file.get("appProperties", {})
        return key in app_properties

    def delete_old_revisions(self, file_id):
        """Remove revisões antigas de um arquivo."""
        # Obter metadados do arquivo para identificar a revisão atual (headRevisionId)
        file_metadata = self.service.files().get(
            fileId=file_id,
            fields="headRevisionId"
        ).execute()
        
        head_revision_id = file_metadata.get("headRevisionId")
        
        if not head_revision_id:
            print("⚠️ Não foi possível identificar a revisão atual do arquivo.")
            return 0
        
        revisions = []

        page_token = None

        while True:

            response = (
                self.service.revisions()
                .list(
                    fileId=file_id,
                    fields=(
                        "nextPageToken,"
                        "revisions(id,keepForever)"
                    ),
                    pageToken=page_token,
                )
                .execute()
            )

            revisions.extend(
                response.get("revisions", [])
            )

            page_token = response.get("nextPageToken")

            if not page_token:
                break

        if len(revisions) <= 1:
            return 0

        deleted = 0

        # Excluir todas as revisões exceto a atual (headRevisionId)
        for revision in revisions:

            revision_id = revision["id"]
            
            # Não excluir a revisão atual
            if revision_id == head_revision_id:
                continue

            try:

                # A API exige que a revisão esteja
                # marcada como Keep Forever antes
                # de permitir a exclusão.
                if not revision.get("keepForever", False):

                    self.service.revisions().update(
                        fileId=file_id,
                        revisionId=revision_id,
                        body={
                            "keepForever": True,
                        },
                    ).execute()

                self.service.revisions().delete(
                    fileId=file_id,
                    revisionId=revision_id,
                ).execute()

                deleted += 1

            except Exception as e:

                print(
                    f"⚠️ Não foi possível remover "
                    f"a revisão {revision_id}: {e}"
                )

        return deleted
