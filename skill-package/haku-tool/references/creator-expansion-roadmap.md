# 영상 스타일 라이브러리 확장 로드맵

## 목적

계정의 겉모습을 복제하지 않고, 여러 영상에서 반복되는 편집 판단을 독립적인 AI 사용 가능 문법으로 추출한다. 새 계정은 Haku와 다른 문제를 해결할 때만 추가한다.

조사 기준일: 2026-07-28

## 우선 조사 후보

| 우선 | 계정 | 배울 편집 문제 | 예상 모듈 | 구현 난도 |
|---:|---|---|---|---|
| 1 | [@samyoukilis](https://www.instagram.com/samyoukilis/) | 일상 행동을 과편집 없이 오래 보게 하는 관찰·연속성 | `observational-micro-story` | 낮음 |
| 2 | [@daniel.schiffer](https://www.instagram.com/daniel.schiffer/) | 제품 행동·카메라 이동·충격점을 광고 리듬으로 전달 | `product-impact-continuity` | 중간 |
| 3 | [@jordi.koalitic](https://www.instagram.com/jordi.koalitic/) | 전경 가림·오브젝트 패스·원근을 촬영 단계에서 전환으로 설계 | `practical-transition-previs` | 중간 |
| 4 | [@macroroom](https://www.instagram.com/macroroom/) | 매크로·슬로모션·실제 물성 변화로 제품 또는 사물을 클라이맥스로 만듦 | `macro-material-climax` | 중간~높음 |
| 5 | [@samkolder](https://www.instagram.com/samkolder/) | 실제 카메라 이동의 방향·속도·공간을 여행 전환으로 연결 | `travel-vector-velocity` | 높음 |
| 6 | [@zachking](https://www.instagram.com/zachking/) | 숨은 컷과 상태 일치로 불가능한 사건을 자연스럽게 보이게 함 | `impossible-continuity` | 높음 |
| 7 | [@buck_design](https://www.instagram.com/buck_design/) | 브랜드 형태·타이포·실사를 하나의 모션 시스템으로 묶음 | `brand-motion-system` | 높음 |
| 8 | [@buildersclub](https://www.instagram.com/buildersclub/) | 실사·3D·그래픽의 혼합 매체 광고 전환 | `mixed-media-product-world` | 매우 높음 |

## 후보 선정 근거

### `@samyoukilis`

- Haku와 가장 가까운 관찰 계열이지만 편집 밀도는 더 낮다.
- 배울 항목:
  - 하나의 미세 행동을 시작부터 끝까지 기다리는 길이
  - 정지 사진처럼 보이지만 내부 행동이 계속되는 구도
  - 장소의 사람·도구·풍습을 짧은 연속으로 묶는 순서
- Haku에 주는 보완: `single-image-sustain`과 `process-observation`의 과편집 방지 기준

### `@daniel.schiffer`

- 제품 광고용 촬영·편집의 연결이 분명하다.
- 배울 항목:
  - 행동 훅 → 제품 디테일 → 사용 반응 → 히어로 샷
  - 실제 카메라 이동을 이용한 방향 전환
  - 충격 순간의 짧은 컷과 곧바로 이어지는 결과 쇼트
- Haku와 분리할 점: 감정적 자연 몽타주가 아니라 제품 기능과 물성 전달이 목적이다.

### `@jordi.koalitic`

- 결과 장면과 제작 과정을 함께 보여 주므로 재현 가능성 판정에 유리하다.
- 배울 항목:
  - 전경 물체가 화면을 가리는 순간의 숨은 컷
  - 렌즈 앞 물체·휴대폰·거울·자전거 같은 실물 전환
  - 최종 프레임을 먼저 설계하고 촬영 동작을 역산하는 방식
- Haku에 주는 보완: 편집에서 억지로 만드는 전환과 촬영으로 해결할 전환을 분리

### `@macroroom`

- 공식 설명상 매크로 촬영, 슬로모션, 실물 효과가 중심이다.
- 배울 항목:
  - 사물의 정상 상태 → 변형 준비 → 물성 사건 → 결과 공개
  - 매크로 ECU와 전체 형태 쇼트의 스케일 교대
  - 실제 현상과 시간 변형을 분리해 기록하는 방법
- Haku에 주는 보완: 물·불꽃·거품을 분위기 인서트가 아니라 인과가 있는 사건으로 만드는 법

### `@samkolder`

- 공식 설명에서 전환·페이싱·사운드 디자인을 고유 편집 스타일의 중심으로 밝힌다.
- 배울 항목:
  - 실제 카메라 이동 벡터를 다음 장소에 전달
  - 속도 램프가 필요한 소스 모션 조건
  - 드론·FPV·하이퍼랩스를 공간 이동 서사로 연결
- 제한: 현재 사용자 자연영상처럼 움직임 메타데이터와 촬영 의도가 부족한 소스에는 바로 적용하지 않는다.

### `@zachking`

- 디지털 슬라이트 오브 핸드와 짧은 시각 서사가 중심이다.
- 배울 항목:
  - 행위 전후의 배우·소품·카메라 위치 일치
  - 가림·팬·신체 동작을 이용한 숨은 컷
  - 첫 프레임의 질문과 마지막 프레임의 즉시 해답
- 제한: 고급 합성 문법이다. 일반 편집 프리셋이 아니라 사전 촬영 설계 모듈로 둔다.

### `@buck_design`

- 브랜드별 형태·방향·모멘텀·매치컷을 재사용 가능한 모션 원칙으로 만든 사례가 명확하다.
- 배울 항목:
  - 브랜드 형태를 전환 규칙으로 변환
  - 타이포와 실사를 같은 운동 법칙으로 통합
  - 여러 비율과 길이에 재조합 가능한 모듈형 모션 시스템
- 제한: 특정 브랜드 디자인을 복제하지 않고 원리와 데이터 구조만 가져온다.

### `@buildersclub`

- 공식 포트폴리오가 3D 모션과 혼합 매체 광고에 집중한다.
- 배울 항목:
  - 실사 제품에서 3D 세계로 넘어가는 재질·조명 일치
  - 제품의 실제 특징을 초현실 공간 규칙으로 확대
  - 라이브액션·CG·타입을 하나의 광고 호로 연결
- 제한: 즉시 자동 편집 대상이 아니라 CG 플레이트와 트래킹이 있는 프로젝트용이다.

## 수집 규칙

1. 계정 전체를 일괄 수집하지 않는다.
2. 사용자가 특정한 공개 단일 `/reel/`, `/p/`, `/tv/` URL만 수집한다.
3. 모든 항목은 기본적으로 `public-reference-only`다.
4. 원본 미디어·음악·로고·문구는 결과물과 저장소에 넣지 않는다.
5. 첫 단계에서는 계정당 5편 이하의 URL만 후보 카드로 만든다.
6. 후보 카드에는 `왜 이 영상이어야 하는가`, `배울 문법`, `필요 촬영본`, `재현 난도`, `반례 가능성`을 적는다.
7. 사용자 승인 뒤에만 단일 URL을 내려받아 로컬 분석한다.

## 규칙 승격 기준

새 편집 문법은 아래를 모두 만족해야 한다.

- 같은 계정의 서로 다른 Reel 3편 이상에서 반복
- 반례 Reel 1편 이상 기록
- Haku의 기존 문법으로 설명되지 않는 고유한 판단이 있음
- 사용자 촬영본으로 재현 가능한 최소 커버리지를 정의
- 효과 이름이 아니라 샷 선택·타이밍·연결·결말 규칙으로 설명 가능
- 테스트 렌더에서 레퍼런스 원본을 사용하지 않음
- 약 4초를 목표로 한 최소 증명 영상에서 기법이 읽힘. 4초로 부족하면 기법이 성립하는 최소 길이만 사용
- 같은 소스의 `plain`과 `proof` 비교에서 차이를 컷 단위로 설명 가능
- 사용자가 `accepted`로 판정

## 확장 구조

새 계정마다 Skill을 바로 만들지 않는다. 먼저 공통 라이브러리에서 문법을 축적한다.

```text
video-style-library
├─ haku_tool
│  ├─ archetypes
│  ├─ edit_grammars
│  └─ operators
├─ observational
├─ product-commercial
├─ practical-transition
├─ travel-velocity
├─ impossible-continuity
└─ brand-motion
```

한 제작물에는 서로 다른 계정 문법을 최대 2개만 사용한다.

- 주 문법: 영상 전체의 컷·연결·결말을 지배
- 보조 문법: 한 시퀀스 또는 한 기능만 담당

## 첫 실행 배치

### 배치 A — 현재 촬영 환경에서 재현성이 높은 계열

1. `@samyoukilis`: 5개 URL 후보
2. `@daniel.schiffer`: 5개 URL 후보
3. `@jordi.koalitic`: 5개 URL 후보

목표: 관찰, 제품 행동, 촬영 기반 전환을 각각 독립 모듈로 분리한다.

### 배치 B — 물성·이동·합성

1. `@macroroom`
2. `@samkolder`
3. `@zachking`

목표: 슬로모션 물성, 카메라 벡터, 숨은 컷의 촬영 조건을 정의한다.

### 배치 C — 광고 모션 시스템

1. `@buck_design`
2. `@buildersclub`

목표: 실사 편집과 별도로 타이포·그래픽·3D 자산이 필요한 광고 모듈을 만든다.

## 다음 산출물

각 배치에서 다음을 만든다.

- `creator-candidate-cards.md`
- `reference-manifest.json`
- `edit-grammar-hypotheses.json`
- `counterexamples.md`
- `coverage-requirements.json`
- `reproduction-test-plan.md`
- `technique-proof-plain.mp4`
- `technique-proof.mp4`
- `technique-proof-storyboard.jpg`
- `technique-proof-explanation.md`
- `technique-proof-verdict.json`
- 사용자 원본으로 만든 테스트 렌더와 크리틱
