# Circuit Atlas · Cadence Circuit Tools

Cadence Virtuoso의 회로 연결을 가져와 확인하고 편집하는 로컬 웹 도구입니다. 회로를 다른 AI에 전달할 수 있는 JSON·Markdown과 SVG도 내보냅니다. Windows 웹 서버와 VMware Linux의 Cadence를 SSH로 연결합니다.

## 구성과 현재 범위

| 주소 | 기능 |
| --- | --- |
| http://127.0.0.1:4173/ | 회로 연결도, 핀·넷 테이블, 편집, 변경 비교, AI 문서 내보내기 |
| http://127.0.0.1:4173/simulation.html | 저장 ADE 넷리스트 실행, 숫자 파라미터·스윕, 파형·FFT, ΣΔ 참고 모델 |
| http://127.0.0.1:4174/ | 프로젝트·블록·스펙 목표, 실제 DC OP·전력, 온도 비교·실행 기록 |

- 심볼은 외부 단자 연결만 표시합니다. 내부 회로를 펼치거나 추정하지 않습니다.
- 웹에서 수정한 연결은 웹 프로젝트에만 적용됩니다. Cadence DB로 쓰지 않습니다.
- 현재 셀 한 단계만 읽으며 버스 확장·inherited net 해석·CDF 계산은 지원하지 않습니다.
- 시뮬레이션은 **저장된 ADE input.scs 복사본**에서 실행합니다. 현재 회로를 새로 netlist 생성하는 기능은 없습니다. W/L 변경은 CDF·면적·둘레를 재계산하지 않습니다.
- ΣΔ 참고 모델의 결과는 실제 Cadence 측정과 별개입니다. Workbench의 PM·잡음·MC·SNDR 등 추가 측정기는 아직 미구현입니다.
- 저장 데이터·개인 회로·PDK·Cadence 설치 파일·SSH 키는 저장소에 포함하지 않습니다.

## 1. 준비

Windows에 **Node.js 22 이상**, **Python 3.12 및 py 런처**, **Windows OpenSSH 클라이언트**, Git을 설치합니다. VM에는 사용 가능한 Virtuoso/Spectre, PDK, SSH 서버가 필요합니다.

기존 검증 환경은 CentOS 6.5 32비트, Python 2.6.6, Virtuoso 6.1.5, Spectre 12.1입니다. 다른 버전에서는 별도 검증이 필요합니다. Cadence/PDK 라이선스와 설치는 사용자가 준비합니다.

VM Linux 터미널에서 IP를 확인합니다. **CIW가 아닌 Linux 터미널**입니다.

```sh
/sbin/ifconfig
```

Windows PowerShell에서 저장소를 복제하고 설치합니다. 예시 IP와 경로를 자신의 VM에 맞게 바꾸세요.

```powershell
git clone https://github.com/scottjsh0128-wq/circuit-atlas.git
cd circuit-atlas
powershell -ExecutionPolicy Bypass -File .\Setup.ps1 -VmAddress 192.168.72.130 -VmUser buet -VmHome /home/buet -SpectrePath /home/buet/cadence/MMSIM121/tools/bin/spectre
```

설치 스크립트는 이 복제본의 기본 VM 경로를 치환합니다. 다른 사용자/경로로 재설정하려면 깨끗한 복제본에서 시작하세요. 전용 RSA 키 생성 시 무인 연결을 원하면 암호 문구를 비워 둡니다. 비밀키는 `work/`에만 보관합니다.

## 2. SSH 연결

첫 연결에서는 VM 호스트 키를 확인하고 등록합니다. VM에서 `ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub`로 지문을 확인할 수 있습니다.

```powershell
ssh -F work/cadence-mcp-ssh/ssh_config -o BatchMode=no -o StrictHostKeyChecking=ask cadence-vm
```

로그인 비밀번호는 **Linux 사용자 계정 비밀번호**입니다. 키가 아직 등록되지 않았다면 Windows PowerShell에서 공개키를 등록합니다.

```powershell
Get-Content work/cadence-mcp-ssh/id_rsa.pub | ssh -F work/cadence-mcp-ssh/ssh_config -o BatchMode=no cadence-vm 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
ssh -F work/cadence-mcp-ssh/ssh_config cadence-vm hostname
```

비밀번호 로그인이 막힌 환경은 `.pub` 파일만 VMware 공유 폴더로 옮긴 뒤 VM 터미널에서 `~/.ssh/authorized_keys`에 추가합니다. `id_rsa` 비밀키는 VM이나 저장소에 업로드하지 마세요.

## 3. VM helper와 CIW

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-VM.ps1
```

Cadence에서 원하는 schematic을 열고 Check and Save한 다음 **CIW**에 입력합니다.

```lisp
load("/home/buet/.circuit-atlas/bridge.il")
```

`VmHome`을 바꿨으면 위 경로도 바꾸세요. Virtuoso를 재시작하거나 추출기를 업데이트한 뒤 다시 로드해야 합니다. 한 Virtuoso 세션에서 사용하세요. 중지는 `caBridgeStop()`입니다.

현재 창은 반드시 **schematic 편집 창**이어야 합니다. ADE/파형 창을 활성화하면 회로 읽기가 실패할 수 있습니다.

## 4. 사이트 실행

```powershell
.\outputs\Start-Circuit-Tools.cmd
```

두 서버를 백그라운드로 실행합니다. 중복 실행은 해당 포트가 이미 사용 중이면 건너뜁니다. 브라우저에서 4173 주소를 열고 **Cadence에서 불러오기 → 현재 회로 읽기 → 이 회로 열기**를 누릅니다.

방향키/빈 화면 드래그로 이동하고, R로 회전, Shift+R로 좌우 반전합니다. 일반 파일 가져오기와 화면 방향키 버튼은 현재 UI에서 제거되어 있습니다. JSON 내보내기는 지원하지만 파일 재가져오기 UI는 없습니다.

로그인 시 자동 시작하려면 `Win+R → shell:startup` 폴더에 `Start-Circuit-Tools.cmd`의 바로가기를 직접 추가합니다. 설치 스크립트가 시스템 시작 설정을 자동 변경하지는 않습니다.

Workbench는 새 설치에서 프로젝트만 생성합니다. 블록을 등록하고 **저장된 ADE 테스트벤치 셀 이름**과 전력 합산 전압원을 지정하세요. 임의의 전원/목표를 자동 설정하지 않습니다.

## 5. MCP 클라이언트 연결 (선택)

웹사이트만 사용하면 별도 MCP 클라이언트 등록이 필요 없습니다. 다른 MCP 클라이언트에는 다음 stdio 실행 정보를 등록합니다. 경로는 실제 복제 위치로 바꾸세요.

```json
{
  "mcpServers": {
    "cadence": {
      "command": "C:/your/path/circuit-atlas/work/cadence-mcp-venv/Scripts/python.exe",
      "args": ["C:/your/path/circuit-atlas/outputs/cadence-mcp/server.py"]
    }
  }
}
```

도구: `cadence_status`, `cadence_get_current_schematic`, `cadence_inspect_saved_simulation`, `cadence_run_saved_simulation`, `workbench_get_state`, `workbench_start_run`, `workbench_cancel_run`. 클라이언트별 등록 형식은 해당 클라이언트 설정에 맞추세요.

## 문제 해결

| 증상 | 확인할 내용 |
| --- | --- |
| 사이트 연결 거부 | Start-Circuit-Tools.cmd 재실행, Node/Python 경로, 각 서버의 stderr 로그 |
| SSH 시간 초과 | VM 실행 여부와 IP 확인. `work/cadence-mcp-ssh/ssh_config`의 HostName 갱신 |
| IP 변경 | 같은 192.168.x 서브넷의 ARP 목록에서 후보를 찾고 기존 호스트 키로 검증하는 보조 탐색이 있습니다. 새 주소가 ARP에 없으면 수동 갱신이 필요합니다. 시뮬레이션 실행 전에는 주소를 갱신하세요. |
| host key 오류 | VM의 지문을 직접 확인. 키 검증을 끄지 마세요. HostKeyAlias는 기존 신뢰 항목을 가리킵니다. |
| 브리지 비활성 | CIW에서 bridge.il 로드. 웹 서버 시작과 CIW load는 서로 다른 단계입니다. |
| 회로 읽기 실패 | schematic 창 활성화, CIW 오류 확인, 편집 명령/대화상자 종료 |
| 이상한 핀/옛 회로 | 최신 helper 설치 → CIW reload → 웹 새로고침 → 새 스냅샷 읽기 |
| 저장 분석 읽기 실패 | VM의 simulation/<cell>/spectre/schematic/netlist/input.scs가 있는지 확인 |

심볼 추출기는 instance terminal 기준입니다. master에만 있는 단자는 생성하지 않으므로, 결과는 심볼 원본의 전체 단자 목록이 아닐 수 있습니다. 핀이 없는 심볼은 단자 정보 없음으로 표시됩니다. 최신 심볼 수정은 JS 검증은 완료했지만 이 릴리스에서 실제 CIW 재로드 검증은 아직 남아 있습니다.

## 데이터와 테스트

- 개인 데이터: `outputs/cadence-mcp/snapshots`, `simulation-results`, `outputs/circuit-workbench/data`. Git에서 제외됩니다.
- Workbench 화면/내보내기는 최근 200개 실행을 조회합니다. 전체 DB는 보존합니다. 백업은 서버와 MCP를 종료하고 DB 및 결과 폴더를 함께 복사하세요.
- 네트워크 공개 서비스가 아닌 localhost 도구입니다. 다른 사용자는 각자의 PC/VM에 설치합니다.

```powershell
npm --prefix outputs/circuit-atlas run check
npm --prefix outputs/circuit-atlas test
npm --prefix outputs/circuit-workbench test
.\work\cadence-mcp-venv\Scripts\python.exe -m unittest discover -s outputs/cadence-mcp -p "test_*.py"
```

웹/모델 테스트는 VM 없이 실행됩니다. 실제 Virtuoso 추출·Spectre 측정 검증은 자신의 VM에서 별도로 수행해야 합니다.
