# Ancient PDF Master

Tesseract OCR 기반 고대 문서 처리 도구. 스캔된 이미지/PDF에서 고대 그리스어, 라틴어, 영어를 OCR하여 검색 가능한 PDF를 생성합니다.

## Features

- **Multi-language OCR**: Ancient Greek (grc), Latin (lat), English (eng) 동시 인식
- **Searchable PDF**: 보이지 않는 텍스트 레이어 오버레이로 검색/복사 가능
- **Bilingual Split**: 대역본 PDF를 언어별로 분할 (공통 페이지 복제 지원)
- **Roman Numeral Numbering**: 로마 숫자(i, ii, iii) + 아라비아 숫자(1, 2, 3) 페이지 넘버링
- **TOC Embedding**: 목차를 PDF 북마크/아웃라인으로 임베딩
- **Multiple Input Formats**: PNG, JPG, TIFF, PDF 지원
- **Electron GUI**: 다크 테마 데스크탑 앱
- **DMG Packaging**: electron-builder로 macOS DMG 빌드 및 GitHub Releases 배포

## Requirements

### System Dependencies

```bash
# macOS
brew install tesseract tesseract-lang poppler python3

# Linux (Debian/Ubuntu)
sudo apt install tesseract-ocr tesseract-ocr-grc tesseract-ocr-lat poppler-utils python3
```

### Node.js

Node.js 18+ and npm

## Quick Install (macOS)

앱 아이콘으로 실행 가능한 `.app` 번들을 빌드하고 `/Applications`에 설치합니다:

```bash
git clone https://github.com/bitswt/Ancient_PDF-Master.git
cd Ancient_PDF-Master
./scripts/install-mac.sh
```

설치 후 **Spotlight (Cmd+Space) → "Ancient PDF Master"** 로 실행하거나 Launchpad에서 클릭하세요.

## Development Mode

`.app` 빌드 없이 바로 실행:

```bash
git clone https://github.com/bitswt/Ancient_PDF-Master.git
cd Ancient_PDF-Master

pip3 install -e .
npm install
npm start
```

또는 원커맨드:

```bash
./scripts/run-dev.sh
```

## Building DMG

배포용 DMG 패키지:

```bash
npm run build:dmg
```

Output: `dist/Ancient PDF Master-1.0.0.dmg`

GitHub Releases 자동 배포는 `package.json`의 `publish` 설정으로 구성되어 있습니다.

## Architecture

```
Electron (GUI)  ←─ IPC ─→  Main Process  ←─ stdio JSON-RPC ─→  Python Backend
renderer.js                 index.js                             bridge.py
index.html                  python-bridge.js                     ocr_engine.py
main.css                    preload.js                           pdf_builder.py
                                                                 pdf_splitter.py
                                                                 page_labels.py
                                                                 toc_builder.py
```

## Project Structure

```
electron/
  main/
    index.js          # Electron main process
    preload.js        # Context bridge (IPC API)
    python-bridge.js  # Python child process management
  renderer/
    index.html        # UI layout
    renderer.js       # Frontend logic
    styles/main.css   # Dark theme styles
src/ancient_pdf_master/
    bridge.py         # stdio JSON-RPC server
    ocr_engine.py     # Tesseract OCR wrapper
    pdf_builder.py    # Searchable PDF generation
    pdf_splitter.py   # Bilingual PDF splitting
    page_labels.py    # Roman/Arabic page numbering
    toc_builder.py    # TOC bookmark embedding
    image_handler.py  # Image/PDF loading
    language.py       # Language pack validation
tests/
    test_*.py         # Unit tests
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
