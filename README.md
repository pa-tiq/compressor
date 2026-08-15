## [github.com/pa-tiq/compressor](https://github.com/pa-tiq/compressor)

Utilitário que comprime vídeos e imagens.
Salva o progresso em um log. Então permite cancelar e depois continuar do ponto onde parou.
`--in-place` substitui o arquivo original pelo arquivo comprimido direto no diretório de origem, _sem backup_. Use com cuidado.

```bash
python3 compress.py origem destino

python3 compress.py --in-place --verbose origem

python3 compress.py -i -v origem

python3 compress.py -i -v /home/usuario/projetos/compressor/Backup

python3 compress.py -i /home/usuario/projetos/compressor/Backup
```

## Requisitos

### Python

Python 3.9 ou superior.

Verifique a instalação:

```bash
python3 --version
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
