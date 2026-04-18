# ClipSyncer

PyQt6와 Fluent Design으로 만든 Windows 클립보드 히스토리 매니저입니다. 종단간 암호화된 GitHub 동기화를 지원합니다.

ClipSyncer는 시스템 트레이에서 동작하며, 복사한 모든 내용을 캡처하고 (선택적으로) 비공개 GitHub 저장소를 통해 여러 기기 간에 암호화된 히스토리를 동기화합니다. 암호화 키는 절대 사용자의 기기를 벗어나지 않습니다.

## 주요 기능

- **실시간 클립보드 모니터링** – 설정 가능한 주기(기본 500ms)로 클립보드에 복사된 텍스트를 캡처합니다.
- **자동 분류** – 항목을 `text`, `url`, `file_path`, `email`로 자동 태그합니다.
- **중복 제거** – SHA-256 콘텐츠 해시로 중복 항목을 자동 제거합니다.
- **AES-256-GCM 암호화** – 모든 클립보드 데이터를 디스크에 저장하거나 업로드하기 전에 암호화합니다.
- **GitHub 동기화 (종단간 암호화)** – 실시간 푸시(5초 디바운스, 최소 30초 간격) + 주기적 풀(60초). GitHub.com과 GitHub Enterprise를 모두 지원합니다.
- **다중 기기 키 유도** – 공유 동기화 비밀번호를 PBKDF2-HMAC-SHA256(60만 회 반복)으로 모든 기기에서 동일한 AES 키로 변환합니다.
- **시스템 트레이 앱** – Fluent Design 트레이 아이콘에서 빠른 작업(히스토리 보기, 모니터링 토글, 수동 동기화, 정리 실행, 종료)을 제공합니다.
- **현대적인 히스토리 뷰어** – 검색, 카테고리 필터, 미리보기, 복사, 삭제, 즐겨찾기, JSON 가져오기/내보내기, 전체 삭제 기능.
- **아카이브 매니저** – 히스토리 크기를 초과한 항목을 로컬에(선택적으로 GitHub에도) 아카이브하며 7일간 보관합니다.
- **정리 서비스** – 주기적인 중복 제거, 오래된 데이터 삭제, SQLite VACUUM을 수행합니다.
- **기업 네트워크 친화적** – 사용자 지정 CA 번들 경로와 SSL 검증 토글로 MITM 프록시 환경을 지원합니다.
- **Windows 자격 증명 관리자 통합** – GitHub 토큰과 암호화 키를 `keyring`으로 저장하며, YAML 파일에는 절대 기록하지 않습니다.

## 요구 사항

- Windows 10 / 11
- Python 3.10 이상 (CI는 3.11에서 빌드)
- 클라우드 동기화를 사용하려면 GitHub 계정 (비공개 저장소 강력 권장)

## 설치

### 옵션 1 – 빌드된 실행 파일 사용

[Releases](../../releases) 페이지에서 `ClipSyncer.exe`를 다운로드하여 실행합니다 (태그된 릴리스에서 GitHub Actions 빌드 워크플로가 생성). Python이 필요하지 않습니다.

### 옵션 2 – 소스에서 실행

```bash
git clone <repository-url>
cd ClipSyncer

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
python main_improved.py
```

편의 스크립트도 제공됩니다:

```bash
run.bat
```

## 빠른 시작

1. ClipSyncer를 실행합니다. 첫 실행 시 환영 다이얼로그가 표시됩니다.
2. **Setup GitHub Storage**(여러 기기 동기화) 또는 **Use Local Storage Only**(로컬 전용)를 선택합니다.
3. GitHub 동기화를 선택했다면 GitHub 설정 다이얼로그를 입력합니다 (아래 참조).
4. ClipSyncer는 시스템 트레이로 최소화됩니다. 무엇이든 복사하면 자동으로 캡처됩니다.
5. 트레이 아이콘 우클릭 → **Show History** (또는 아이콘 더블클릭)로 항목을 탐색합니다.

### 키보드 단축키 (히스토리 뷰어)

| 단축키   | 동작                          |
| -------- | ----------------------------- |
| `Ctrl+C` | 선택한 항목을 클립보드로 복사 |
| `Ctrl+F` | 검색창 포커스                 |
| `Delete` | 선택한 항목 삭제              |
| `F5`     | 목록 새로 고침                |
| `Esc`    | 창 닫기 (앱은 트레이에 유지)  |

### 트레이 메뉴

- 히스토리 보기 (Show History)
- 모니터링 토글 (캡처 일시 정지/재개)
- GitHub 동기화 (수동 푸시)
- 정리 실행 (Run Cleanup)
- 종료 (Quit)

## GitHub 동기화 설정

1. **비공개 저장소 생성** – GitHub.com이나 GitHub Enterprise 인스턴스에 비공개 저장소(예: `clipboard-backup`)를 만듭니다. 암호화된 클립보드 데이터를 저장하므로 반드시 비공개로 유지합니다.
2. **Personal Access Token 생성**
   - `Settings → Developer settings → Personal access tokens → Tokens (classic)`로 이동합니다.
   - `repo` 스코프로 토큰을 생성합니다.
3. **ClipSyncer 설정**
   - 트레이 또는 히스토리 뷰어에서 **GitHub Sync Settings**를 엽니다.
   - 저장소(`username/repo` 또는 전체 URL), 토큰을 입력하고 **동기화 비밀번호**를 설정합니다.
   - **Test Connection**을 클릭한 뒤 저장합니다.
4. **모든 기기에서 동일한 동기화 비밀번호**로 반복 설정하여 모든 기기가 같은 AES 키를 유도하고 서로의 항목을 읽을 수 있도록 합니다.

### GitHub Enterprise

`github_settings.yaml`에 `github.enterprise_url`(예: `https://github.example.com`)을 설정합니다. 클라이언트는 `/{enterprise_url}/api/v3` 엔드포인트를 사용합니다.

### 기업 TLS / MITM 프록시

- `github.ca_bundle_path`: 회사 루트 CA가 포함된 PEM 번들 경로.
- `github.verify_ssl`: 최후의 수단일 때만 `false`로 설정합니다.
- 클라이언트는 `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE` 환경 변수도 인식하며, 마지막으로 `certifi`를 폴백으로 사용합니다.

## 설정

설정은 두 개의 파일로 분리되어 있으며 모두 `%APPDATA%/ClipboardHistory/` 아래에 위치합니다:

- `settings.yaml` – 애플리케이션 설정 (`config/default_settings.yaml`을 기반으로 생성)
- `github_settings.yaml` – GitHub 관련 설정 (예시: `config/github_settings_example.yaml`)

비밀 정보(GitHub 토큰, 암호화 키)는 `keyring`을 통해 **Windows 자격 증명 관리자**에 저장되며, YAML에는 절대 기록되지 않습니다.

### 전체 기본값

```yaml
clipboard:
  check_interval: 500        # 클립보드 폴링 간격 (ms)
  max_history_size: 500      # 아카이브 전 보관 최대 항목 수
  auto_start: true

encryption:
  enabled: true
  algorithm: AES-256-GCM

storage:
  retention_days: 30         # 이보다 오래된 항목은 삭제
  backup_interval: 86400     # 초 (24시간)
  database_path: null        # null → %APPDATA%/ClipboardHistory/clipboard.db

github:
  enabled: false
  repository: ""             # "username/repo" 또는 전체 URL
  token: ""                  # YAML이 아닌 keyring에 저장
  sync_interval: 3600        # 레거시
  auto_sync: false           # 레거시 – 실시간 푸시 + 주기적 풀이 사용됨
  pull_interval: 60          # 풀 간격 (초)
  push_debounce: 5           # 클립보드 변경 후 푸시까지 대기 시간 (초)
  min_push_interval: 30      # 푸시 사이 최소 간격 (초)
  ca_bundle_path: ""         # 기업 CA 번들 (PEM)
  verify_ssl: true           # 폐쇄된 기업망에서만 비활성화
  # enterprise_url: ""       # 예: https://github.example.com

cleanup:
  enabled: true
  duplicate_removal: true
  cleanup_interval: 3600     # 정리 실행 간격 (초)

ui:
  show_notifications: true
  minimize_to_tray: true
  start_minimized: false
  theme: light               # light | dark

logging:
  level: INFO                # DEBUG | INFO | WARNING | ERROR
  file_logging: true
  max_log_size: 10485760     # 파일당 10 MB
  max_log_files: 5
```

## 데이터 및 로그 위치

| 항목                | 경로                                                                |
| ------------------- | ------------------------------------------------------------------- |
| 설정                | `%APPDATA%/ClipboardHistory/settings.yaml`                          |
| GitHub 설정         | `%APPDATA%/ClipboardHistory/github_settings.yaml`                   |
| SQLite 데이터베이스 | `%APPDATA%/ClipboardHistory/clipboard.db`                           |
| 로컬 아카이브       | `%APPDATA%/ClipboardHistory/archives/`                              |
| 일별 로그           | `%APPDATA%/ClipboardHistory/logs/ClipSyncer_YYYY-MM-DD.log`         |
| 최신 로그 (10 MB)   | `%APPDATA%/ClipboardHistory/logs/ClipSyncer_latest.log`             |
| 암호화 키           | Windows 자격 증명 관리자 (`keyring` 통해)                           |
| GitHub 토큰         | Windows 자격 증명 관리자 (`keyring` 통해)                           |

`%APPDATA%`가 설정되지 않은 상태로 소스에서 실행할 경우 로그는 `./logs/`로 폴백됩니다.

## 아키텍처

```
ClipSyncer/
├── main_improved.py          # 진입점 – 앱과 트레이를 오케스트레이션
├── build.py                  # PyInstaller 빌드 + 선택적 NSIS 인스톨러 스크립트
├── ClipSyncer.spec           # PyInstaller 스펙 (qfluentwidgets 후크 포함)
├── hook-qfluentwidgets.py    # PyInstaller 런타임 후크
├── requirements.txt          # 개발 + 런타임 의존성
├── requirements-prod.txt     # 런타임 전용 의존성
├── run.bat                   # 개발용 런처 (venv 활성화)
├── version_info.txt          # Windows 버전 리소스
├── config/
│   ├── default_settings.yaml
│   └── github_settings_example.yaml
├── assets/
│   └── icon.ico
├── src/
│   ├── core/
│   │   ├── clipboard/        # ClipboardMonitor, ClipboardHistory, ClipboardEntry
│   │   ├── encryption/       # EncryptionManager (AES-256-GCM), KeyManager (keyring + PBKDF2)
│   │   ├── storage/          # DatabaseManager (SQLAlchemy), ClipboardRepository
│   │   ├── interfaces.py     # ABC: EncryptionStrategy, SyncBackend, StorageBackend
│   │   └── exceptions.py     # ClipSyncerError 계층
│   ├── services/
│   │   ├── component_factory.py   # 컴포넌트 연결 (DI)
│   │   ├── sync_coordinator.py    # 양방향 푸시 / 풀 / 병합
│   │   ├── auto_sync_service.py   # 실시간 푸시 (디바운스) + 주기적 풀
│   │   ├── archive_manager.py     # 초과/오래된 항목 아카이브
│   │   ├── sync/github_sync.py    # GitHubSyncService (Enterprise 지원)
│   │   └── cleanup/               # CleanupService, DuplicateRemover, OldDataCleaner
│   ├── ui/
│   │   ├── tray/             # Fluent Design 시스템 트레이 아이콘
│   │   ├── history/          # ModernHistoryViewer (qfluentwidgets)
│   │   └── dialogs/          # Welcome, GitHub settings, App settings, Restore
│   └── utils/
│       └── config_manager.py # settings.yaml + github_settings.yaml 로드 및 병합
├── tests/                    # pytest 테스트 스위트 (17개 모듈)
└── .github/workflows/build.yml  # CI: .exe 빌드 후 릴리스에 첨부
```

### 주요 설계 결정

- **의존성 역전** – 핵심 코드는 ABC(`EncryptionStrategy`, `SyncBackend`, `StorageBackend`)에 의존하며, 구체 클래스(예: `GitHubSyncService`)는 `ComponentFactory`로 주입됩니다.
- **단일 파일 동기화 모델** – 원격 상태는 단일 암호화 JSON(`backups/clipboard_sync.json`)에 저장되며, 푸시 시 덮어쓰고 풀 시 병합됩니다.
- **GitHub를 기본 저장소로 사용** – 동기화가 활성화되면 `SyncCoordinator.initial_sync()`가 시작 시 로컬 캐시를 비우고 GitHub에서 풀하여 저장소를 진실의 원천으로 취급합니다.
- **Qt 스레드 안전성** – 백그라운드 작업은 데몬 스레드에서 실행되며, UI 업데이트는 시그널/슬롯을 통해 Qt 이벤트 루프로 전달하는 `QtSignalBridge`를 거칩니다.

## 자동 동기화 동작

- **푸시:** 캡처된 모든 클립보드 변경에서 트리거됩니다. 5초 동안 디바운스(가장 최근 것이 우선)되며, 30초당 최대 1회로 제한됩니다.
- **풀:** 백그라운드 타이머가 60초마다 GitHub에서 풀합니다 (`pull_interval`로 설정 가능). 시작 후 5초 뒤 초기 풀이 실행됩니다.
- **수동 동기화:** 트레이 메뉴에서 사용 가능하며, 디바운스를 우회합니다.

## 보안 모델

- 클립보드 콘텐츠는 SQLite에 기록되거나 업로드되기 전에 **AES-256-GCM**(인증된 암호화)으로 암호화됩니다.
- AES 키는 **PBKDF2-HMAC-SHA256**(60만 회 반복)으로 **동기화 비밀번호**에서 유도되므로 어떤 기기에서든 동일한 비밀번호는 동일한 키를 생성합니다.
- 키와 GitHub 토큰은 **Windows 자격 증명 관리자**에 저장되며, 유도된 산출물만 디스크에 닿습니다.
- 잘못된 동기화 비밀번호는 명확한 메시지와 함께 `DecryptionError`를 발생시킵니다 – 조용한 손상은 없습니다.
- **반드시 비공개 GitHub 저장소를 사용하세요.** 저장소에는 암호문만 보관되지만 그래도 공개해서는 안 됩니다.

## 개발

### 테스트 실행

```bash
pytest                    # 전체 테스트
pytest -v                 # 상세 출력
pytest tests/test_github_sync.py
pytest --cov              # 커버리지 (pytest-cov는 requirements.txt에 고정됨)
```

### 린트 / 포매팅 / 타입 검사

```bash
black .
flake8
mypy .
```

### Windows 실행 파일 빌드

```bash
python build.py
```

이 스크립트는:

1. `build/`와 `dist/`를 정리합니다.
2. `version_info.txt`를 다시 생성합니다.
3. `pyinstaller ClipSyncer.spec --clean --noconfirm`을 실행합니다.
4. `dist/ClipSyncer.exe`를 출력합니다.
5. 전통적인 인스톨러를 만들 수 있도록 `makensis installer.nsi`로 컴파일할 수 있는 `installer.nsi` NSIS 스크립트를 작성합니다.

### CI

`.github/workflows/build.yml`은 `main`/`master`로의 푸시와 PR마다 실행 파일을 빌드하며, `v*` 패턴 태그에 대해 `ClipSyncer.exe`를 GitHub Release에 첨부합니다.

## 문제 해결

- **"GitHub 동기화가 작동하지 않음"** – `github.enabled: true`이고 `repository`가 `username/repo` 형식(전체 URL이 아님)인지 확인합니다. GitHub 설정 다이얼로그의 **Test Connection**을 사용하세요.
- **"DecryptionError: wrong encryption key"** – 동기화 비밀번호가 데이터 암호화에 사용된 비밀번호와 일치하지 않습니다. 다른 기기에서 사용한 동일한 비밀번호를 입력하세요.
- **빌드된 exe에서 qfluentwidgets 임포트 오류** – `python build.py`로 다시 빌드합니다. `ClipSyncer.spec`은 `collect_data_files('qfluentwidgets')`로 필요한 자산을 번들링합니다.
- **기업 프록시 뒤에서 SSL 오류** – `github.ca_bundle_path`를 회사 CA 번들로 설정하거나 `REQUESTS_CA_BUNDLE`을 export합니다. 최후의 수단으로 `github.verify_ssl: false`를 설정합니다.
- **로그는 어디 있나요?** – `%APPDATA%/ClipboardHistory/logs/ClipSyncer_latest.log` (그리고 일별 회전 파일).

## 라이선스

MIT License.
