# Haku Operator Registry v3

## 구조

Haku Tool의 범용 핵심은 특정 전환·분할 화면·플레어가 아니라 여러 작품에서 반복되는 장면 판단 다섯 개다.

| Core Operator | 기능 | 현재 상태 |
|---|---|---|
| `sensory-scale-relay` | 물성 ECU/CU → 사람 MS → 관계·공간 WS/EWS로 감정을 재해석 | corpus supported / proof pending |
| `density-wave-release` | 기준 이미지 → 짧은 밀집 → 호흡·해방의 파동 | research pass / user accepted 1 situation |
| `motif-state-return` | 모티프를 상태·스케일·주체를 바꿔 세 번 이상 귀환 | corpus supported / proof pending |
| `subject-withholding-reveal` | 손·등·실루엣으로 주체를 보류한 뒤 새 정보와 함께 공개 | corpus supported / proof pending |
| `afterimage-handoff` | 인물·행동의 주도권을 움직이는 빛·물성·공간 잔상에 이양 | corpus supported / proof pending |

## 조건부 장치

- `action-prism-continuity`: 마스터 행동·디테일·반응·결과 커버리지가 모두 있을 때만 쓴다.
- `memory-panel-poem`: 같은 사건의 기억 단위를 한 화면에서 병렬화할 때만 쓴다.
- `luminous-gaze-sustain`: 한 숏 안의 실제 표정·빛·초점 변화가 충분할 때만 쓴다.
- `negative-space-phrase-gate`: 암전의 기능을 중단·보류·장 전환 중 하나로 명시할 때만 쓴다.

조건부 장치는 Haku 식별성의 필요조건이 아니며, 단일 evidence family만으로 범용 승격하지 않는다.

## 라우팅

1. 목적·감정·광고 기능을 먼저 적는다.
2. 원본의 사람·날·장소·행동 일관성을 검사한다.
3. ECU/CU/MS/WS, 마스터 행동, 반응, 흔적, 열린 종료 커버리지를 표로 만든다.
4. Core Operator 하나를 주 문법으로 선택한다.
5. 다른 Core Operator 또는 조건부 장치는 하나만 보조로 허용한다.
6. safe·recommended·experimental을 먼저 설계한다.
7. 같은 원본·같은 길이의 plain/proof로 하나의 규칙만 검증한다.
8. 원본→plain→proof→모든 컷 경계→모든 화면 내부 사건 경계를 직접 본다.
9. 사용자 `accepted` 전에는 범용 Operator로 승격하지 않는다.

## 절대 금지

- 전환만 바꾸고 장면 안의 행동·빛·물성·관계를 설계하지 않는 편집
- 같은 프레임 반복, 마지막 프레임 패딩, 길이 보충용 자동 줌
- 서로 무관한 예쁜 자연 스톡 혼합
- Haku 원본 영상·음악·문구·서체·레이아웃 복제
- 한 작품 또는 같은 촬영 family의 파생본을 여러 독립 증거로 계산

## v006 검증 위치

- `motif-state-return`: `C:\Users\HP-5600G\Desktop\AI 제작과정\vcd-output\haku-tool-completion-v006\hero\summer-memory-v006\proof.mp4`
- `memory-panel-poem`: 같은 영상의 1.00초, 1.52초, 2.04초 순차 moving-window 사건
- 이벤트 프레임: `C:\Users\HP-5600G\Desktop\AI 제작과정\vcd-output\haku-tool-completion-v006\hero\summer-memory-v006\event-strips\event-atlas.jpg`
- AI 판정: `technically_valid`, 사용자 판정 `pending`
- 승격 진행: `density-wave-release = 1/3 accepted situations`; 다른 Operator는 `0/3`

이 proof는 material ID 집합·파일 경로·hash·source anchor의 동일성을 검증한다. plain/proof의 실제 사용 길이·횟수·타임라인 range는 다르므로 동일 range라고 주장하지 않는다.
