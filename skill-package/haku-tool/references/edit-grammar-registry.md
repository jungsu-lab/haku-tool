# haku_tool 편집 문법 레지스트리

## 목적

`archetype`은 영상이 무엇을 느끼게 하고 어떤 사건을 다루는지 설명한다. `edit grammar`는 촬영된 쇼트를 시간·화면·행동 관계로 어떻게 연결하는지 설명한다. 둘을 같은 말로 취급하지 않는다.

예:

- `seasonal-poetic-essay × organic-flow-essay`
- `seasonal-poetic-essay × graphic-memory-log`
- `action-prism-human-narrative × action-prism-continuity`
- `minimal-single-idea × single-image-sustain`

같은 소재와 색보정이어도 편집 문법이 다르면 다른 스타일이다.

## 선택 구조

한 결과물은 아래 구조로 선택한다.

1. `archetype`: 1개
2. `primary_edit_grammar`: 1개
3. `secondary_operator`: 0~1개
4. `motion_policy`: `source-motion-only`, `motivated-digital-motion`, `composite-required` 중 1개
5. `ending_policy`: `open-space`, `material-afterimage`, `graphic-close`, `completed-action` 중 1개

여러 편집 문법을 동일 비중으로 섞지 않는다. 주 문법이 보이지 않으면 스타일을 구현한 것으로 판정하지 않는다.

## 상태

- `implemented`: 사용자 촬영본으로 렌더하고 역비교한 문법
- `corpus-supported`: 복수 Reel에서 반복되지만 사용자 촬영본 테스트 전
- `candidate`: 반복 증거가 제한적이거나 합성·재촬영 조건이 커서 추가 검증 필요
- `special-device`: 독립 스타일이 아니라 특정 기능에만 쓰는 장치

## 최소 증명 영상

새 편집 문법을 긴 완성본에 넣기 전에 `technique proof clip`으로 분리 검증한다.

- 목표 길이: 약 4초
- 허용 길이: 기법의 준비·변화·결과가 읽히는 최소 길이. 보통 3~8초이며 필요한 경우에만 12초까지 늘린다.
- 원칙: 시간을 4초에 억지로 맞추지 않는다. 기법이 성립하는 가장 짧은 길이를 사용한다.
- 한 영상의 주제: 주 편집 문법 1개 또는 보조 연산자 1개
- 권장 쇼트 수: 2~6개. `burst-breathe-montage`처럼 파편 수가 본질인 경우만 예외
- 오디오: 사용자가 요청하지 않으면 넣지 않는다.
- 디지털 줌·프리즈·속도 램프: 검증 대상이 아니면 사용하지 않는다.

각 기법은 같은 원본 구간으로 아래 두 영상을 만든다.

1. `plain`: 의미 관계를 설계하지 않은 가장 단순한 연결
2. `proof`: 선택한 편집 문법 하나만 적용한 연결

함께 제공할 설명:

- `기법 이름`
- `화면에서 볼 지점`
- `각 컷이 일어난 이유`
- `plain보다 달라진 의미`
- `성립에 필요했던 촬영본`
- `실패하면 어떻게 보이는지`
- `Haku 증거 Reel`

사용자 판정은 `accepted`, `partial`, `rejected` 중 하나로 기록한다. `accepted` 전에는 사용자용 프리셋으로 승격하지 않는다.

## 주 편집 문법

### 1. `haku_tool.edit.organic-flow-essay`

- 한국어 이름: 자연 흐름 에세이
- 상태: `implemented`
- 적합 유형: `seasonal-poetic-essay`, `minimal-single-idea`
- 중심 원리: 원본 안의 바람·물·빛·카메라 이동을 보존하고, 모티프가 돌아올 때만 컷의 의미를 바꾼다.
- 시간 구조: 감각 훅 → 느슨한 이동 → 짧은 상승 군집 1회 → 넓은 잔상
- 컷 판단: 행동의 시작·종료, 방향 변화, 밝기 변화, 물성의 변형
- 움직임 정책: `source-motion-only`가 기본값
- 전환 정책: 하드컷과 자연스러운 이미지 라임이 기본값
- 결말: WS/EWS, 빈 공간, 물결·하늘·나뭇잎 같은 지속 운동
- 증거 Reel:
  - #6 `DaUibIhzFkf`: 긴 호흡, 반사·빛의 연결, 인물에서 공간으로 해방
  - #17 `DXzIEytzWhP`: 투과·반사·실루엣으로 장소를 묶음
  - #20 `DWoUT9rk1ry`: 계절을 거리·높이·명암으로 변주
  - #30 `DQrTzfpk9iR`: 사물 모티프와 이동 방향의 반복
  - #36 `DLmsnfszuQc`: 적은 쇼트로 장소와 색의 시간 진행
- 필수 촬영본: 방향이 읽히는 자연 움직임, CU와 WS, 최소 1개 반복 모티프, 종료용 넓은 쇼트
- 금지:
  - 전 쇼트 자동 줌
  - 샷 끝 프레임 복제
  - 이유 없는 속도 램프
  - 장소만 교체하는 균일 컷
- 합격 기준: 디지털 움직임을 제거해도 이미지 관계와 정서 진행이 남는다.

### 2. `haku_tool.edit.burst-breathe-montage`

- 한국어 이름: 감각 폭발과 호흡
- 상태: `corpus-supported`
- 적합 유형: `sensory-flash-montage`, 상승 구간이 있는 `seasonal-poetic-essay`
- 중심 원리: 짧은 파편을 계속 이어 붙이지 않고, 밀집 군집과 숨 쉴 쇼트를 대비시킨다.
- 시간 구조: 1~3초 앵커 → 0.13~0.50초 파편 군집 → 0.8~3초 호흡 → 변형된 군집 또는 잔상
- 컷 판단: 스케일 점프, 빛의 충돌, 같은 물성의 다른 상태, 방향 반복
- 움직임 정책: `source-motion-only`
- 증거 Reel:
  - #1 `DbS9D2JziFP`: 짧은 감각 군집과 긴 중간 호흡의 대비
  - #8 `DZXiQ_jz2tg`: 물·빛·실루엣 파편의 고밀도 연결
  - #11 `DOdPyazk0k7`: ECU·CU·WS 스케일 점프 뒤 집단 이미지 공개
  - #19 `DWuZaCfE-WF`: 물·해·숲·불꽃을 물성으로 결속한 플래시 몽타주
  - #31 `DQi8EW5k0-o`: 78쇼트 초고속 변형의 극단 사례
- 필수 촬영본: 최소 20개의 쓸 수 있는 파편, ECU/CU/WS, 반복 가능한 색·형태·물성 2종 이상
- 금지:
  - 촬영본이 부족한데 같은 클립을 임의 확대해 샷 수를 늘림
  - 모든 구간을 0.2초대로 자름
  - 모티프 없이 빠르기만 복제
- 합격 기준: 무음으로 봐도 각 군집 안의 이미지 공통점과 군집 사이의 호흡 차이가 보인다.

### 3. `haku_tool.edit.action-prism-continuity`

- 한국어 이름: 행동 프리즘 연속성
- 상태: `corpus-supported`
- 적합 유형: `action-prism-human-narrative`, `process-observation`
- 중심 원리: 하나의 작은 행동을 마스터·세부·반응·결과로 분해하되 인과를 잃지 않는다.
- 시간 구조: 행동 예고 → 시작 → 손·도구·표정 세부 → 상대 또는 환경 반응 → 결과 → 공간 이탈
- 컷 판단: 손이 닿기 직전, 물체가 가려지는 순간, 시선 전환, 행동 결과가 드러나는 순간
- 움직임 정책: `source-motion-only`; 합성은 사전 설계된 경우만 허용
- 증거 Reel:
  - #3 `Da24ipMTXu4`: 고정된 공간 안에서 실제 수행의 진행으로 리듬 생성
  - #10 `DOyJ6k3Ewmb`: 작은 행동과 관계를 구름·공간의 긴 호흡으로 감쌈
  - #12 `DaxG1n-TWOv`: 자전거·사진 행동을 등·손·발·옆얼굴·와이드로 분해
  - #14 `DYrhH-6zH-1`: 제품과 학생 행동을 마스터·인서트·반응으로 연결
  - #22 `DVdX-WBk4L5`: 두 인물의 관계를 행동과 반응으로 전개
  - #38 `DJrTFPaTXHI`: 학교생활의 여러 행동을 긴 관계 서사로 확장
- 필수 촬영본: 같은 행동의 WS/MS/CU, 시작 전·종료 후 핸들, 반응, 결과 쇼트
- 금지:
  - 서로 다른 테이크의 손 위치·진행 방향이 충돌
  - 결과 없는 동작 인서트 나열
  - 행동이 멈춘 프레임을 길이 보충용으로 복제
- 합격 기준: 쇼트를 섞어도 관객이 누가 무엇을 왜 했고 무엇이 달라졌는지 설명할 수 있다.

### 4. `haku_tool.edit.graphic-memory-log`

- 한국어 이름: 기억 기록창
- 상태: `corpus-supported`
- 적합 유형: `graphic-layout-memory-log`
- 중심 원리: 검정 여백, 작은 프레임, 위치 이동, 표식, 독자 문구를 장식이 아니라 사건의 간격과 기록 체계로 사용한다.
- 시간 구조: 표식 또는 공백 → 작은 영상 조각 → 위치·크기 변형 → 반복 표식 → 그래픽 종료
- 컷 판단: 프레임 출현·소멸, 기록 단위 전환, 문장과 이미지의 의미 대응
- 움직임 정책: `motivated-digital-motion`; 프레임 이동은 정해진 규칙을 따라야 한다.
- 증거 Reel:
  - #2 `DbQf99sT2rh`: 검정 여백과 좁은 가로 창으로 행동을 기록
  - #5 `DaX8TkKzqIH`: 시간 표식과 분리된 장면 조각
  - #16 `DX6n8iQPsjQ`: 다중 패널·질감·문구의 기억 배열
  - #25 `DS5xPk1E_NT`: 붉은 시간 표식과 작은 가로 영상의 교대
  - #29 `DRJvMoQk6Cy`: 프레임 위치·크기의 출현과 소멸을 컷 리듬으로 사용
  - #32 `DPqzqkwE9zP`: 반복 표식을 장면 간 아이덴티티 앵커로 사용
- 필수 촬영본: 중앙·측면 안전 여백이 있는 소스, 잘려도 의미가 유지되는 행동, 독자 그래픽 시스템
- 금지:
  - 레퍼런스의 문구·시간 코드·서체·레이아웃 복제
  - 이유 없이 모든 샷을 작은 창에 넣음
  - 세로 원본의 핵심 행동을 가리는 크롭
- 합격 기준: 그래픽을 제거하면 기록 구조가 무너지고, 그래픽을 유지하면 각 조각의 순서가 설명된다.

### 5. `haku_tool.edit.single-image-sustain`

- 한국어 이름: 단일 이미지 지속
- 상태: `corpus-supported`
- 적합 유형: `minimal-single-idea`, `process-observation`
- 중심 원리: 강한 하나의 행동·빛·구도·물성을 오래 보고 한 번의 변형만 크게 준다.
- 시간 구조: 강한 이미지 제시 → 내부 변화 관찰 → 스케일 또는 추상도 변화 1회 → 잔상
- 권장 쇼트 수: 2~6
- 컷 판단: 실제 행동 단계, 표정 변화, 빛의 변화, 구체에서 추상으로 넘어가는 순간
- 증거 Reel:
  - #15 `DYql5NyTBeO`: 탑뷰와 긴 그림자, 엔드카드
  - #18 `DXJ2bohkzbV`: 제작 과정의 실제 변화와 세부 인서트
  - #24 `DTXxF7Fk9rO`: 얼굴·눈·플레어만으로 정서 호 구성
  - #28 `DRUNg3UE0c2`: 건축 구도 안 인물 위치 변화
  - #34 `DOTAz9lE11A`: 수중 행동에서 추상 수면 질감으로 한 번 전환
  - #37 `DLaEqK0TisL`: 같은 불꽃을 물성·관계·잔상으로 변주
  - #40 `DJGM0LsTdxY`: 꽃·민들레·모자의 원형 라임을 5쇼트로 완성
- 필수 촬영본: 오래 볼 만한 내부 변화 또는 구도, 충분한 실제 지속 시간
- 금지:
  - 장면이 약하다는 이유로 디지털 줌을 계속 추가
  - 움직임 없는 마지막 프레임을 길이 보충
  - 의미가 없는 컷어웨이 삽입
- 합격 기준: 컷을 더 줄여도 핵심 이미지의 힘이 유지되고, 추가 효과 없이도 변화가 읽힌다.

### 6. `haku_tool.edit.ellipsis-trace-space`

- 한국어 이름: 행동·흔적·공간 생략
- 상태: `corpus-supported`
- 적합 유형: 짧은 `action-prism-human-narrative`, `minimal-single-idea`
- 중심 원리: 사건 전체를 보여 주지 않고 원인, 남은 흔적, 사건 뒤 공간의 세 단계로 관객이 빈칸을 채우게 한다.
- 시간 구조: 행동 또는 시선 → 남겨진 사물·변화 → 넓은 공간 또는 이탈
- 권장 쇼트 수: 3~7
- 증거 Reel:
  - #27 `DR4qWQ8E6Kc`: 교실 행동 → 남겨진 사물 → 도시 WS
  - #35 `DLrwgLYzr7T`: 시선 → 고립 → 회전하는 해방 동작
  - #37 `DLaEqK0TisL`: 불꽃 → 관계 → 손에 남은 잔상
- 필수 촬영본: 원인과 흔적의 명확한 대응, 결말용 공간
- 금지:
  - 원인과 관계없는 풍경을 시적인 결말로 오인
  - 관객이 사건을 추론할 단서가 하나도 없음
- 합격 기준: 대사를 추가하지 않아도 세 이미지 사이의 인과 또는 감정 방향을 추론할 수 있다.

## 보조 연결 연산자

### `haku_tool.operator.motif-rhyme-chain`

- 기능: 형태·색·방향·물성을 3회 이상 변형 귀환시킨다.
- 증거: #7의 물·원형·손, #30의 유리병·도로 거울·빛, #37의 불꽃·수면 반사·손 불꽃, #40의 꽃·민들레·모자
- 사용 조건: 각 귀환이 이전과 다른 스케일·장소·의미를 가져야 한다.
- 실패: 같은 소재를 반복 재생하기만 함

### `haku_tool.operator.crescendo-rupture-release`

- 기능: 긴 관찰 또는 중간 호흡을 유지하다 한 번의 짧은 파열 뒤 공간을 연다.
- 증거: #9의 긴 관계 장면 → 불꽃 마이크로 군집 → 구름·이탈, #13의 불꽃 확대 → 백색 폭발
- 사용 조건: 파열 전 축적과 파열 후 해방 쇼트가 모두 있어야 한다.
- 실패: 영상 전체를 파열 구간으로 만듦

### `haku_tool.operator.optical-layer-memory`

- 상태: `candidate`
- 기능: 반사·유리·수면·실루엣·이중노출을 같은 기억 층으로 연결한다.
- 증거: #6, #17
- 사용 조건: 반사 또는 투과 소스가 실제 촬영되었거나 합성용 플레이트가 있다.
- 실패: 무관한 두 영상을 낮은 불투명도로 겹침

### `haku_tool.operator.black-interruption`

- 상태: `special-device`
- 기능을 먼저 하나로 고정한다:
  - `punctuation`: 사건 중단
  - `negative-space`: 작은 프레임의 무대
  - `record-card`: 표식·문구 제시
  - `chapter-break`: 시간 또는 장소 전환
- 코퍼스 수치: 40편 중 27편에서 암전 구간이 검출됐지만 기능이 서로 다르다.
- 금지: 암전이 자주 보였다는 이유만으로 모든 컷 사이에 검정 프레임 삽입

## 후보 장치

아래 항목은 독립 프리셋으로 승격하지 않는다.

- #4 `DakPIs6zMDl`의 글리치 파열: 단일 강한 사례이므로 `special-device`
- #39 `DJKFdm6TKL1`의 방향축 초고속 추진: 강한 사례지만 동일 문법의 복수 시각 판정 전 `candidate`
- 의도적 프리즈: 자동 정지 추정치가 실제 고정 촬영과 섞여 있으므로 타임라인 재생 확인 전 사용 금지
- 역재생: 화면 증거와 실제 재생을 함께 확인한 경우만 기록

## 편집 문법 선택 게이트

1. 촬영본에서 실제로 긴 호흡을 버틸 쇼트를 찾는다.
2. 같은 행동의 WS/MS/CU가 있으면 `action-prism-continuity`를 후보에 둔다.
3. 쓸 수 있는 파편이 20개 이상이고 반복 모티프가 2종 이상이면 `burst-breathe-montage`를 후보에 둔다.
4. 여백 안전 소스와 독자 그래픽 규칙이 있으면 `graphic-memory-log`를 후보에 둔다.
5. 2~6개 쇼트만으로 하나의 변화가 충분하면 `single-image-sustain`을 우선한다.
6. 원인·흔적·공간이 대응하면 `ellipsis-trace-space`를 후보에 둔다.
7. 자연 움직임과 모티프 귀환, 종료용 공간이 있으면 `organic-flow-essay`를 후보에 둔다.
8. 후보 중 재촬영 가정이 가장 적은 하나를 주 문법으로 선택한다.

## 출력 필드

`edit-grammar-selection.json`에는 최소한 다음을 기록한다.

```json
{
  "archetype": "seasonal-poetic-essay",
  "primary_edit_grammar": "haku_tool.edit.organic-flow-essay",
  "secondary_operator": "haku_tool.operator.motif-rhyme-chain",
  "motion_policy": "source-motion-only",
  "ending_policy": "open-space",
  "evidence_reels": [],
  "required_coverage": [],
  "missing_coverage": [],
  "excluded_devices": [],
  "selection_reason": "",
  "confidence": 0.0
}
```

## 다음 검증 순서

1. `single-image-sustain`: 가장 강한 자연 쇼트 2~5개로 약 4~7초 증명 영상
2. `burst-breathe-montage`: 자연영상에서 20개 이상 파편이 확보될 때 약 5~8초 증명 영상
3. `graphic-memory-log`: 독자 그래픽을 먼저 설계한 뒤 약 5~8초 증명 영상
4. `action-prism-continuity`: 사람 또는 제품 행동의 다중 거리 촬영 후 약 4~8초 증명 영상
5. `ellipsis-trace-space`: 원인·흔적·종료 공간을 새로 촬영한 뒤 약 4~7초 증명 영상

각 단계는 `plain → proof → 프레임 설명 → 사용자 판정` 순서로 종료한다.
