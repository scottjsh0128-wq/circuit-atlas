# Circuit Atlas v1 데이터 계약

이 앱의 목적은 회로 연결을 명시적으로 검토·편집·전달하는 것입니다. Cadence의 심벌, 배선 좌표, 전기적 동작을 그대로 에뮬레이션하지는 않습니다.

## 입력 1: CIW 텍스트

아래 구조를 지원합니다. 헤더 하나, 소자 선언, 파라미터, 핀 연결 순입니다.

```text
=== my_cell / schematic ===
M1  (cell=nmos1v)
   l = 500n
   w = 5u
   D -> out
   B -> VSS
   G -> in
   S -> VSS
```

- 마지막의 `(db:0x... db:0x...)` 반환값 목록만 명시적으로 무시합니다.
- 알 수 없는 줄, 중복 소자/핀/파라미터는 오류로 표시합니다. 조용히 생략하지 않습니다.
- `nil`, `null` 연결은 JSON null로 변환합니다. 실제로 그런 이름의 넷이 있다면 JSON 입력을 사용하세요.
- 이름과 파라미터 문자열을 그대로 보존합니다. `VDD`, `VSS`를 global로 추정하지 않습니다.
- 텍스트에 없는 포트, 방향, 라이브러리, 원본 좌표, implicit 핀은 알아낼 수 없습니다.
- 소자 타입은 generic으로 시작합니다. D/G/S/B의 의미나 심벌을 셀 이름만으로 확정하지 않습니다.

## 입력 2: JSON

```json
{
  "schema": "circuit-atlas/1",
  "top": "lib/cell/schematic",
  "source": {"type": "cadence-ciw"},
  "cells": [{
    "id": "lib/cell/schematic", "name": "cell", "library": "lib", "view": "schematic",
    "nets": [{"name": "out", "global": false}],
    "ports": [{"name": "OUT", "direction": "output", "net": "out"}],
    "instances": [{
      "id": "M1", "name": "M1", "library": "pdk", "cell": "nmos4", "kind": "generic",
      "orientation": "R0", "sourcePosition": [1.2, 3.4],
      "parameters": {"w": "5u", "l": "500n"},
      "pins": [{"name": "D", "net": "out"}, {"name": "G", "net": null}]
    }]
  }]
}
```

- 인스턴스 id와 name은 셀 안에서 각각 고유합니다. 넷/포트/핀 이름도 각 스코프에서 고유합니다.
- 핀의 net은 **해당 셀의 nets에 선언된 정확한 이름** 또는 null입니다. 이름 비교는 대소문자를 구분합니다.
- 인스턴스 `child`에 실제 존재하는 cells.id를 넣으면 하위 셀 열기가 가능합니다. 개별 셀 추가만으로 자동 계층 바인딩하지 않습니다.
- 여러 셀은 따로 시각화합니다. 계층 flattening / config view resolution / global 전파는 하지 않습니다.
- 버스 `data<7:0>`, 배열 이름, numBits는 보존하되 비트별 확장·대응은 미검증으로 표시합니다.
- sourcePosition과 orientation은 메타데이터입니다. 편집기 좌표는 프로젝트 layout에 따로 저장합니다.
- 최대 20 MB, 200셀, 셀당 1,500소자. 아주 큰 셀은 가독성과 속도 때문에 분할을 권장합니다.

## CIW 추출 스크립트 범위

`cadence-export.il`은 현재 활성 schematic의 instances, master terminals, instTerms의 net, 셀 terminals, nets, 원문 instance properties를 읽습니다. 먼저 Check and Save로 DB 연결을 갱신해야 합니다. 스크립트는 schematic을 수정·저장하지 않습니다.

현재 셀 한 단계만 추출합니다. CDF의 기본값/계산값, netSet/inherited connections, ADE spec/시뮬레이션 결과, config 바인딩, 버스 member 매핑, PDK 심벌 그래픽은 추출하지 않습니다. 문자열의 따옴표·역슬래시·줄바꿈·탭·CR을 이스케이프합니다. 비표준 제어문자가 포함된 속성은 JSON 검사에서 오류가 날 수 있습니다. Virtuoso 런타임이 없는 환경에서 작성했으므로 **실환경 첫 실행 검증이 필요합니다**.

API 근거:
- [Cadence: Read and follow nets](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/14209/read-and-follow-nets)
- [Cadence: Port name and instTerms](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/62475/how-to-get-the-port-name-of-a-selected-cell-view)
- [Cadence: master terminals and pin coordinates](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/40374/how-to-find-the-coordinates-of-an-instance-s-pin)

## 출력

- 현재 구조 JSON: 다시 가져올 수 있는 연결 기준 데이터.
- 프로젝트 JSON: current + baseline + layout + review. 다시 가져올 때 검토 표시는 초기화합니다.
- AI Markdown: 해석 규칙, 검토 상태, 넷별 모든 연결점, 미연결, 경고, 변경 내역, 전체 JSON.
- 변경 JSON: 사람이 검토하는 의미 기반 경로. RFC 6902 실행 패치나 Cadence 쓰기 명령이 아닙니다.
- SVG: 현재 셀 전체 그래프. 핀 이름과 넷이 기준이며 선 교차는 접속을 의미하지 않습니다.

자동 저장은 브라우저 로컬 저장소에만 남습니다. 서버·외부 모델로 회로를 전송하는 코드는 없습니다. 원본 파일과 프로젝트 파일을 별도로 보관하세요.

## 후속 확장 경계 (구현하지 않음)

후속 VMware/MCP 수집기는 v1 JSON을 반환하는 어댑터로 연결하고, 기존 validate/parseImport와 같은 검증 경로를 거쳐야 합니다. 실제 Cadence 쓰기는 별도 명시적 변경 검토·트랜잭션 계층이 필요합니다. 스펙은 셀/인스턴스 id를 참조하는 별도 문서로 두고 회로 연결 데이터와 분리합니다. 현재는 MCP, VMware 연결, spec 가져오기, 외부 LLM 호출을 구현하지 않았습니다.

### 화면 방향 (0.1.1)

프로젝트의 layout[cellId][JSON.stringify([kind,id])]에는 x/y와 함께 rotation(0/90/180/270), mirrored(boolean)를 저장합니다. 기본값은 0/false입니다. 중심 기준 회전 후의 화면 좌우 반전은 rotation의 부호를 바꾸고 mirrored를 반전시킵니다. 순수 표시 속성이므로 원본 orientation, 연결 JSON, 회로 diff에는 영향을 주지 않습니다. SVG와 프로젝트에는 화면 방향이 반영됩니다.
