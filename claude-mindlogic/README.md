# Claude Code에 Mindlogic 모델 추가하기

[mindlogic-codex-setup](https://github.com/Phjrab/mindlogic-codex-setup)의 Claude Code 버전입니다. 기존 Claude 로그인과 모델은 **그대로 두고**, `mindlogic/...` 모델을 **추가**합니다.

- `claude`: 지금과 완전히 같습니다. 아무것도 바꾸지 않습니다.
- `claude-ml`: 같은 Claude Code를 로컬 라우터(`127.0.0.1:18763`)를 거쳐 실행합니다.
  - `mindlogic/`로 시작하는 모델 → Mindlogic Gateway(`/v1/gateway/responses`, Codex 설정과 같은 경로)
  - 그 밖의 모델(`claude-...`) → 기존 Anthropic 로그인 그대로 Anthropic으로 전달
- 한 세션 안에서 `/model`로 두 공급자를 오갈 수 있습니다.

## 설치 (Windows)

준비물: Claude Code(`claude` 명령), Python 3.10 이상과 `py` 런처, Git.

PowerShell에서 아래를 그대로 실행합니다.

```powershell
git clone -b claude/token-connection-setup-zwc3gg https://github.com/scottjsh0128-wq/circuit-atlas.git "$env:TEMP\claude-mindlogic-src"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\claude-mindlogic-src\claude-mindlogic\Install-ClaudeMindlogic.ps1"
```

설치 스크립트가 하는 일:
- `%USERPROFILE%\.claude\mindlogic\`에 파일을 복사하고, 이 폴더를 사용자 PATH에 추가합니다.
- `FACTCHAT_API_KEY`를 환경변수, `%USERPROFILE%\.claude\mindlogic.env`, `%USERPROFILE%\.codex\.env` 순서로 찾습니다. 없으면 한 번 입력받아(화면에 표시 안 됨) `%USERPROFILE%\.claude\mindlogic.env`에 저장합니다.
- 키로 사용 가능한 Mindlogic 모델을 조회해 `claude-ml`의 `/model` 선택 창에 `Mindlogic · ...` 항목으로 추가합니다(`picker-settings.json`). 계정에 모델이 추가되면 설치 스크립트를 다시 실행하세요.
- 선택 창에 보일 모델만 고르려면 `-Models "gpt-6-sol,gpt-6-luna"`처럼 지정합니다. 선택은 `models.txt`에 저장되어 다음 설치에도 유지되고, `-AllModels`로 전체 목록으로 되돌립니다.

### 일반 `claude`와 데스크톱 앱 Code 탭에도 추가 (`-Global`)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\claude-mindlogic-src\claude-mindlogic\Install-ClaudeMindlogic.ps1" -Global
```

- `%USERPROFILE%\.claude\settings.json`에 라우터 주소와 선택 창 항목을 추가합니다(수정 전 백업 생성). Claude 모델은 여전히 본인 로그인으로 Anthropic에 가고, `mindlogic/...`만 Mindlogic으로 갑니다.
- 라우터가 Windows 로그인 때 자동으로 켜지도록 시작프로그램에 등록합니다. **라우터가 꺼져 있으면 일반 `claude`도 동작하지 않습니다.**
- 되돌리기: 같은 명령에 `-Global` 대신 `-RemoveGlobal`. `claude-ml`은 계속 쓸 수 있습니다.
- claude.ai 웹/데스크톱 앱의 **일반 채팅**은 외부 모델을 지원하지 않아 추가할 수 없습니다.

설치 후 **새 터미널**을 여세요. 복사한 소스 폴더(`%TEMP%\claude-mindlogic-src`)는 지워도 됩니다.

macOS/Linux에서는 `claude-ml`(bash) 파일을 PATH에 링크해서 같은 방식으로 씁니다.

## 동작 방식과 보안

- 라우터는 `127.0.0.1`에서만 듣고, `claude-ml`이 만든 로컬 토큰(`~/.claude/mindlogic-router.token`)이 있는 요청만 받습니다.
- Mindlogic 키는 Mindlogic 요청에만, Anthropic 인증은 Anthropic 요청에만 전달합니다. 로컬 토큰은 외부로 보내지 않습니다.
- 로그(`~/.claude/mindlogic-router.log`)에는 모델·HTTP 상태만 남고 키와 대화 내용은 기록하지 않습니다.
- Mindlogic 쪽은 Anthropic 요청을 Responses 형식으로 변환합니다(텍스트, 이미지, 도구 호출 지원). 모델이 바뀌면 이전 `thinking` 블록은 넘기지 않습니다. 토큰 수 계산(`count_tokens`)은 근사값입니다.
- 키 변경은 `.env` 파일만 고치면 다음 요청부터 반영됩니다.

## 문제 해결

- **Mindlogic HTTP 402**: 키의 잔액·사용량을 확인하세요. Anthropic으로 자동 우회하지 않습니다.
- **라우터 시작 실패**: `%USERPROFILE%\.claude\mindlogic-router.log.err`를 확인하세요.
- **라우터 멈추기**: 백그라운드에서 계속 돕니다(`claude-ml`을 실행하면 자동으로 다시 켜짐). 멈추려면 PowerShell에서
  `Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | ? CommandLine -like '*mindlogic*router.py*' | % { Stop-Process -Id $_.ProcessId }`
- **Claude 모델이 `claude-ml`에서만 인증 오류**: 평소처럼 `claude`로 쓰면 됩니다. Mindlogic 모델은 `claude-ml`에서만 필요합니다.
