# Claude Code에 Mindlogic 모델 추가하기

[mindlogic-codex-setup](https://github.com/Phjrab/mindlogic-codex-setup)의 Claude Code 버전입니다. 기존 Claude 로그인과 모델은 **그대로 두고**, `mindlogic/...` 모델을 **추가**합니다.

- `claude`: 지금과 완전히 같습니다. 아무것도 바꾸지 않습니다.
- `claude-ml`: 같은 Claude Code를 로컬 라우터(`127.0.0.1:18763`)를 거쳐 실행합니다.
  - `mindlogic/`로 시작하는 모델 → Mindlogic Gateway(`/v1/gateway/responses`, Codex 설정과 같은 경로)
  - 그 밖의 모델(`claude-...`) → 기존 Anthropic 로그인 그대로 Anthropic으로 전달
- 한 세션 안에서 `/model`로 두 공급자를 오갈 수 있습니다.

## 설치 (macOS, Python 3.11+)

1. **API 키**: Codex 설정 때 만든 `~/.codex/.env`의 `FACTCHAT_API_KEY`를 그대로 읽습니다. 따로 할 일이 없습니다.
   Codex 설정이 없다면 `~/.claude/mindlogic.env`에 `FACTCHAT_API_KEY=발급받은_키` 한 줄을 넣고 `chmod 600 ~/.claude/mindlogic.env`를 실행하세요.
2. 이 폴더를 받고 명령어를 등록합니다.

   ```bash
   git clone -b claude/token-connection-setup-zwc3gg https://github.com/scottjsh0128-wq/circuit-atlas.git
   mkdir -p ~/.local/bin
   ln -sf "$PWD/circuit-atlas/claude-mindlogic/claude-ml" ~/.local/bin/claude-ml
   ```

   `~/.local/bin`이 PATH에 없다면 `~/.zshrc`에 `export PATH="$HOME/.local/bin:$PATH"`를 추가하세요.

## 사용

```bash
claude-ml                                   # 평소처럼 Claude 모델로 시작
claude-ml --model mindlogic/gpt-6-luna      # Mindlogic 모델로 시작
```

세션 안에서 `/model mindlogic/gpt-6-sol`, `/model claude-sonnet-5-5`처럼 바꿀 수 있습니다. 모델 이름은 Mindlogic 계정의 모델 ID 앞에 `mindlogic/`을 붙인 것입니다.

첫 실행 시 `isn't described by this version's model catalog` 안내가 한 번 나올 수 있습니다. Claude Code가 모르는 모델이라는 뜻이며 동작에는 문제없습니다.

## 동작 방식과 보안

- 라우터는 `127.0.0.1`에서만 듣고, `claude-ml`이 만든 로컬 토큰(`~/.claude/mindlogic-router.token`)이 있는 요청만 받습니다.
- Mindlogic 키는 Mindlogic 요청에만, Anthropic 인증은 Anthropic 요청에만 전달합니다. 로컬 토큰은 외부로 보내지 않습니다.
- 로그(`~/.claude/mindlogic-router.log`)에는 모델·HTTP 상태만 남고 키와 대화 내용은 기록하지 않습니다.
- Mindlogic 쪽은 Anthropic 요청을 Responses 형식으로 변환합니다(텍스트, 이미지, 도구 호출 지원). 모델이 바뀌면 이전 `thinking` 블록은 넘기지 않습니다. 토큰 수 계산(`count_tokens`)은 근사값입니다.
- 키 변경은 `.env` 파일만 고치면 다음 요청부터 반영됩니다.

## 문제 해결

- **Mindlogic HTTP 402**: 키의 잔액·사용량을 확인하세요. Anthropic으로 자동 우회하지 않습니다.
- **라우터 시작 실패**: `~/.claude/mindlogic-router.log`를 확인하세요. 멈추려면 `pkill -f claude-mindlogic/router.py`.
- **Claude 모델이 `claude-ml`에서만 인증 오류**: 평소처럼 `claude`로 쓰면 됩니다. Mindlogic 모델은 `claude-ml`에서만 필요합니다.
