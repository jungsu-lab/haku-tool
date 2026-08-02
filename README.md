# Haku Auto Research

이 폴더는 기존 `haku-tool`의 렌더러와 Operator를 교체하지 않는다. 공개 레퍼런스 연구, 가설 생성, 반례 탐색, proof 우선순위와 사용자 승인 이력을 관리하는 상위 연구 계층이다.

## 원칙

1. 자동 수치는 연구 순서를 정할 뿐 의미를 확정하지 않는다.
2. `semantic_complete`는 전체 시퀀스의 직접 시각 검토와 최소 3개 시간 근거가 있어야 한다.
3. 관찰과 해석을 분리한다.
4. 하나의 효과가 아니라 3개 이상 독립 작품에서 반복되는 조합만 계정 문법 후보가 된다.
5. 반례가 없는 가설은 검증된 가설이 아니다.
6. 공개 Haku 미디어는 `public-reference-only`이며 결과 영상과 promoted pack에 넣지 않는다.
7. proof에는 사용자 소유·commissioned·licensed 원본만 사용한다.
8. 한 번의 수정 루프에서 원인 가설은 최대 4개만 바꾼다.
9. 사용자 `accepted` 전에는 Operator를 승격하지 않는다.
10. 서로 다른 3개 상황의 승인이 범용 Operator 승격의 최소 조건이다.

## 연구 루프

`ingest → prioritize → direct visual review → semantic card → cross-work synthesis → counterexample search → proof design → render → direct comparison → correction`

## 상태 파일

- `state/research-state.json`: 40개 작품의 연구 진행 상태
- `state/research-queue.json`: 다음 직접 검토 배치
- `reviews/<reel-id>.json`: 작품별 전체 시퀀스 의미 카드
- `synthesis/hypotheses.json`: 반복 조합과 반례
- `experiments/`: plain/proof 실험 계약과 결과

자동 연구가 정지하더라도 위 파일을 통해 다음 실행이 같은 지점에서 재개된다.

