# Timeline Grammar Dataset

영상 모음은 레퍼런스 보관소일 뿐이다. 편집 문법 데이터셋이 되려면 작품 전체 의미와 정확한 시간 구간의 기술·목적·감정 효과가 연결되어야 한다.

## 계층

`account → reel → narrative sequence → timeline event → Operator → proof cycle → user verdict`

- `reel`: 작품 전체의 목적, 시퀀스 호, 소재 적합성
- `timeline event`: 정확한 시작·종료 시간 안에서 관찰되는 쇼트·컷·타이밍·효과
- `Operator`: 여러 작품에서 반복되는 원인→편집 선택→시청자 효과
- `proof cycle`: 무편집 원본에서 같은 문법이 실제로 재현되는지 plain/proof로 검증
- `user verdict`: 서로 다른 세 상황에서의 명시적 승인

## 이벤트 작성 원칙

1. 한 이벤트는 하나의 지배적인 편집 의도를 가진다.
2. 시간 범위는 실제 영상 안에 있어야 하며 종료가 시작보다 커야 한다.
3. `observation`에는 직접 확인한 화면·파형 사실만, `inference`에는 기능과 예상 반응만 적는다.
4. 효과가 없으면 필드를 생략하지 않고 `none` 또는 `not_present`로 기록한다.
5. 오디오를 듣지 않았으면 beat, bass hit, sound anchor를 추정하지 않는다. 사용자가 보류했으면 `deferred_by_user`, 권리 확인 중이면 `deferred_by_rights`와 `not_reviewed`를 사용한다.
6. `purpose`에는 효과 이름, 사용 시점, 적용 장면, 사용 이유, 시청자 느낌을 모두 기록한다.
7. 자동 측정은 재검토 후보만 제시한다. 이벤트 확정은 주 에이전트의 직접 시각 검토가 필요하다.
8. 한 효과가 여러 목적을 가져도 `primary`는 하나만 고른다.
9. 레퍼런스 수치를 그대로 복사하지 않고 사용자 원본과 목적에 맞게 Operator가 재계산한다.
10. schema `1.1` proof와 final edit는 전체 `narrative_arc`에서 hook, setup, buildup, climax, resolution, CTA를 모두 판정한다. 없는 단계도 삭제하지 않고 `not_applicable`과 이유를 기록한다.
11. schema `1.1`에서는 10개 축의 키만 채우는 것으로 통과하지 않는다. 샷·컷·타이밍·색·모션의 결정값, 장면 연결 이유, 시청자 반응을 비어 있지 않은 관찰값으로 기록한다.
12. `licensed_library_track`을 사용하면 `audio_rights_manifest`와 `music_event_map`을 연결하고, beat position·sound anchor·music·beat·volume curve를 실제 검토값으로 채운다.
13. 편집 툴은 결과에 맞게 선택한다. 단순 컷·프레임 검증은 deterministic renderer, 마스크·트래킹·화면 내부 합성은 Fusion, 색·믹싱·최종 마스터는 Resolve를 우선하되 사용 이유를 `toolchain`에 기록한다.
14. schema `1.1`은 `timeline_duration_seconds`와 `timeline_fps`를 가지며, 각 이벤트의 `source_mapping`에 원본 clip ID·경로·SHA-256·source in/out·source/output frame range·retime 여부를 기록한다. 다중 원본에서 `source_duration_seconds` 하나로 provenance를 대체하지 않는다.

## 저장 위치

- 레퍼런스: `timeline-grammar/<reel_id>.json`
- proof: `proofs/<cycle_id>/timeline-grammar.json`
- 구조 템플릿: `references/timeline-grammar-event.template.json`
- 검증: `scripts/validate_timeline_grammar.py`
- 오디오 권리 검증: `scripts/validate_audio_rights.py`
- 음악-화면 사건 검증: `scripts/validate_music_event_map.py`

기존 `semantic-review`는 작품 전체 해석을 담당하며 이 레이어로 대체하지 않는다. 두 층을 `reel_id`로 연결한다.
