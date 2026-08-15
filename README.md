## [github.com/pa-tiq/compressor](https://github.com/pa-tiq/compressor)

Utilitário que comprime vídeos, imagens e pdfs.
O programa permite cancelar (Ctrl+C) e depois continuar do ponto onde parou.

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

## Aceleração por GPU NVIDIA (NVENC)

Se você tiver uma placa NVIDIA disponível, o script detecta e usa automaticamente o encoder por GPU (NVENC) na compressão de **vídeos**, que é a parte mais lenta do processo. Não precisa passar nenhuma flag extra: se a GPU e o driver responderem corretamente, o `hevc_nvenc` (ou `h264_nvenc`, como alternativa) é usado; caso contrário, o script cai automaticamente para `libx265`/`libx264` via CPU, como antes.

Requisitos:

1. Driver NVIDIA instalado (`nvidia-smi` precisa funcionar):

   ```bash
   nvidia-smi
   ```

2. ffmpeg compilado com suporte a NVENC. Verifique com:

   ```bash
   ffmpeg -encoders | grep nvenc
   ```

   Se não aparecer nada, o ffmpeg do seu sistema (via `apt`, por exemplo) provavelmente não tem suporte a NVENC. Nesse caso, uma opção é instalar a versão estática oficial, que já vem com NVENC habilitado:

   ```bash
   wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
   tar xf ffmpeg-release-amd64-static.tar.xz
   sudo cp ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
   sudo cp ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
   ```

3. Drivers de vídeo NVIDIA atualizados o suficiente para o codec desejado (HEVC/NVENC costuma exigir GPUs Pascal ou mais recentes; GPUs mais antigas podem só suportar `h264_nvenc`, que o script já tenta como alternativa).

Ao rodar, se a GPU for detectada e funcional, você verá no início da execução:

```
🚀 GPU NVIDIA detectada. Usando hevc_nvenc (NVENC).
```

Se a GPU existir mas o NVENC não responder (driver desatualizado, ffmpeg sem suporte, etc.), o script avisa e volta para CPU automaticamente:

```
⚠️ GPU NVIDIA encontrada, mas o NVENC não respondeu (driver/ffmpeg sem suporte). Usando CPU.
```

## Compressão de arquivos locais

Uso rápido (comprime direto na pasta, substituindo os arquivos originais)

```bash
python3 compress.py -i /home/usuario/projetos/compressor/Backup
```

O `-i`/`--in-place` serve para comprimir arquivos substituindo os originais. Sem esse modo, origem e destino são obrigatórios. O `-v`/`--verbose` serve para mostrar os logs de compressão.

Exemplos:

```bash
python3 compress.py origem destino

python3 compress.py --in-place --verbose origem

python3 compress.py -i -v /home/usuario/projetos/compressor/videos

python3 compress.py -v /home/usuario/projetos/compressor/Backup /home/usuario/projetos/compressor/Comprimidos

```

Para PNG, HEIC e HEIF, a conversão para JPG também altera o nome/extensão do arquivo.

## Compressão de arquivos do Google Drive

1. No [Google Cloud Console](https://console.cloud.google.com/), ative a [Google Drive API](https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com).
2. Google Drive API -> Gerenciar -> Credenciais -> Criar credenciais -> opção "ID do cliente OAuth" -> tipo "App para computador".
3. Salve o arquivo JSON como `credentials.json` na pasta desse repositório.
4. Talvez você precise adicionar o seu e-mail em [Público-alvo](https://console.cloud.google.com/auth/audience) -> Usuários de teste.

O processamento do Google Drive deve ser direcionado para uma pasta específica através do --drive-folder-id.

Por exemplo: Em `https://drive.google.com/drive/folders/19Hghzx13WFNfV1Dg5govNvGzYSjJSF6z`, o ID da pasta é `19Hghzx13WFNfV1Dg5govNvGzYSjJSF6z`.

```bash
python3 compress.py --drive --drive-folder-id "19Hghzx13WFNfV1Dg5govNvGzYSjJSF6z"
```

O programa lista os arquivos da pasta **recursivamente** (inclui todas as subpastas), baixa cada arquivo temporariamente para o pc, comprime localmente, compara o tamanho original com o tamanho comprimido, envia de volta para o Google Drive se ele ficar menor e remove os arquivos temporários após o processamento.

Para evitar compressão repetida, o programa ignora arquivos marcados como já comprimidos em `.drive_logs` e também marca arquivos já comprimidos no `appProperties` do Google Drive.

O sistema de cache funciona em dois níveis:

- **Logger local (`.drive_logs/`)**: Permite retomar processamentos interrompidos
- **appProperties do Drive**: Marca permanentemente arquivos já processados no próprio Google Drive

Arquivos marcados com `appProperties` são completamente pulados em execuções subsequentes, pois já foram processados anteriormente e tiveram suas revisões deletadas (se `--drive-delete-revisions` foi usado).

Se quiser remover permanentemente as revisões anteriores dos arquivos processados, use o seguinte comando:

```bash
python3 compress.py --drive --drive-folder-id "19Hghzx13WFNfV1Dg5govNvGzYSjJSF6z" --drive-delete-revisions
```

O `--drive-delete-revisions` tem precedência absoluta (exceto sobre arquivos marcados no `appProperties`):

- **Deleção prévia**: Deleta revisões antigas de todos os arquivos não marcados antes do processamento
- **Deleção pós-upload**: Deleta a versão anterior criada pelo upload bem-sucedido

Arquivos já marcados no `appProperties` são completamente pulados, pois já tiveram suas revisões deletadas em execuções anteriores e já estão com tamanho otimizado.

A utilização do `--drive-delete-revisions` implica que o conteúdo anterior do arquivo não poderá ser recuperado pelo histórico de versões.
