## [github.com/pa-tiq/compressor](https://github.com/pa-tiq/compressor)

Utilitário que comprime vídeos, imagens e pdfs.
Salva o progresso em um log. Então permite cancelar e depois continuar do ponto onde parou.
`--in-place` substitui o arquivo original pelo arquivo comprimido direto no diretório de origem, _sem backup_. Use com cuidado.

### Estrutura do Projeto

- `compress.py` - Script principal com interface de linha de comando
- `config.py` - Constantes e configurações do sistema
- `utils.py` - Funções utilitárias (verificação de dependências, detecção de codecs)
- `drive_client.py` - Cliente Google Drive (autenticação e operações de arquivo)
- `drive_processor.py` - Processamento de arquivos do Google Drive
- `compressor.py` - Classe principal de compressão de arquivos

## Requisitos

### Python

Python 3.9 ou superior.

Verifique a instalação:

```bash
python3 --version
```

Crie uma venv, ative-a e instale os requirements.txt nela:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ffmpeg, libheif e ghostscript

Os 3 são obrigatórios. `libheif` pra HEIC e HEIF, `ghostscript` pra pdf, `ffmpeg` pro resto.

No Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg libheif-examples ghostscript
```

Verifique:

```bash
ffmpeg -version
heif-convert --version
ghostscript -version
```

## Compressão de arquivos locais

Uso rápido (comprime direto na pasta, substituindo os arquivos originais)

```bash
python3 compress.py -i /home/usuario/projetos/compressor/Backup
```

O `--in-place` serve para comprimir arquivos substituindo os originais. Sem esse modo, origem e destino são obrigatórios.

Exemplos:

```bash
python3 compress.py origem destino

python3 compress.py --in-place --verbose origem

python3 compress.py /home/usuario/projetos/compressor/Backup /home/usuario/projetos/compressor/Comprimidos

```

Para PNG, HEIC e HEIF, a conversão para JPG também altera o nome/extensão do arquivo.

## Compressão de arquivos do Google Drive

1. No [Google Cloud Console](https://console.cloud.google.com/), ative a [Google Drive API](https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com).
2. Na seção Credenciais, selecione Criar credenciais e escolha a opção "ID do cliente OAuth", do tipo "App para computador".
3. Salve o arquivo JSON como `credentials.json` na pasta desse repositório.

O processamento do Google Drive deve ser direcionado para uma pasta específica através do --drive-folder-id.

Por exemplo: Em `https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz`, o ID da pasta é `1AbCdEfGhIjKlMnOpQrStUvWxYz`.

```bash
python3 compress.py --drive --drive-folder-id "1AbCdEfGhIjKlMnOpQrStUvWxYz"
```

O programa lista os arquivos da pasta, baixa cada arquivo temporariamente para o pc, comprime localmente, compara o tamanho original com o tamanho comprimido, envia de volta para o Google Drive se ele ficar menor e remove os arquivos temporários após o processamento.

Se quiser remover permanentemente as revisões anteriores dos arquivos atualizados, use o seguinte comando:

```bash
python3 compress.py --drive --drive-folder-id "1AbCdEfGhIjKlMnOpQrStUvWxYz" --drive-delete-revisions
```

Depois disso, o conteúdo anterior não poderá ser recuperado pelo histórico de versões.
