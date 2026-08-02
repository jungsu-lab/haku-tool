---
name: haku-tool
description: "@haku_.photo의 공개 Reel 코퍼스에서 반복 가능한 연출·촬영·영상미·편집·색·사운드 문법을 증거 기반으로 추출하고, 영상 목적과 소재 적합성을 먼저 판정한 뒤 콘셉트·인물 동선·미세 행동·샷 리스트·커버리지·hero edit·색보정·사운드 구조·크리틱을 만든다. 모든 proof와 완성 편집을 narrative·shot·cut·timing·transition·text·color·audio·motion·purpose의 시간 구간별 10축으로 설계·검증하고, 필요하면 권리가 확인된 기존 공개 무료 음원을 사용한다. 청춘·계절·관계·감각 필름을 설계하거나, 스토리 없이도 강한 영상미와 연출이 필요한 광고, 촬영본의 Haku 계정 식별성과 광고 부합성을 검증할 때 사용한다."
---

# haku_tool

## 시간 연속성 품질 게이트

모든 신규 plain/proof 렌더는 `scripts/temporal_continuity_qc.py`를 통과해야 한다.
`render_proof_recipe.py`와 `render_composite_proof_recipe.py`는 렌더 직후 이 검사를
fail-closed로 실행하고, `run_proof_cycle.py`는 경계·내부 이벤트 manifest를 만든 뒤
허용된 편집 이벤트를 반영해 다시 검사한다.

- 전체 디코딩 프레임 해시로 완전 중복과 마지막 프레임 패딩을 찾는다.
- 160x90 grayscale MAD로 코덱의 chroma 변화가 있어도 3 transition 이상 이어지는
  마지막 근정지 구간을 실패 처리한다.
- 미기록 motion spike, scale jump, scale reset은 자동 미학 판정이 아니라 직접 볼
  evidence strip 후보로 기록한다.
- 기록된 컷·패널·내부 편집 이벤트 주변 프레임만 예외로 허용한다.
- 자동 실패가 하나라도 있으면 proof-cycle은 `review-ready`가 아니다.
- 통과는 기술적 연속성만 뜻하며 Haku다움, 연출·영상미, 전체 재생 검토,
  사용자 acceptance 또는 Operator 승격을 증명하지 않는다.
- 렌더 및 검사 프로세스의 스레드는 2개 이하로 제한한다.

## 최상위 작업 계약

`C:\Users\HP-5600G\Desktop\AI 제작과정` 아래에서 작업할 때는 다른 분석·계획·렌더 전에 `REFERENCE_BASED_VIDEO_WORK_CONTRACT.md`를 전부 읽는다.

우선순위는 `현재 사용자 지시 → 최상위 작업 계약 → Haku Skill·references → 자동 측정·기술 검사`다. Haku의 컷 길이나 전환 타이밍을 맞추는 것을 재현으로 보고하지 않는다. 목적·감정·촬영본의 강점·한 컷 내부 사건·장면 인과·오디오가 범위에 있을 때의 음악 상호작용·마지막 잔상을 먼저 평가한다. 기술 오류 0개는 출발선일 뿐 좋은 편집의 증거가 아니다.

## 목적

haku_.photo의 고유 영상·음악·인물·문구를 복제하지 말고, 여러 Reel에서 반복 검증된 연출 판단을 사용자 영상에 맞게 전이한다. `video-creative-director`를 공통 실행 엔진으로 사용하고 이 Skill은 haku 계열 문법과 촬영 지시를 제공한다.

판단 우선순위는 연출, 영상미, 편집 완성도, 계정 식별성, 광고 부합성이다. 스토리는 선택 사항이다. 작업 전 [purpose-fit.md](references/purpose-fit.md)를 읽고 `@haku_.photo`와 소재 적합성을 기록한다.

## 절대 규칙

1. 공개 레퍼런스는 `public-reference-only`로 로컬 분석에만 사용한다.
2. 레퍼런스 원본 영상·음악·인물·로고·문구를 최종 결과물이나 저장소에 넣지 않는다.
3. 한두 Reel에서만 본 장치를 전체 스타일 규칙으로 일반화하지 않는다.
4. 컷 수만 맞추고 연출을 재현했다고 판정하지 않는다.
5. 촬영되지 않은 인물 행동·관계·빛·공간을 편집 효과로 복구할 수 있다고 주장하지 않는다.
6. 규칙마다 Reel ID, 타임코드, 관찰, 추론, 필요한 촬영본, 반례, 신뢰도를 기록한다.
7. 조회수는 성과 참고값일 뿐 연출 규칙의 증거로 사용하지 않는다.
8. 사용자 결과물에는 독자적인 음악·사운드 디자인만 사용한다.
9. 사용자가 오디오를 보류하면 오디오 스트림·사운드 플랜·소리 축 평가는 만들지 않고 `deferred_by_user`로 기록한다.
10. 이전 결과물을 덮어쓰지 않고 `v001`, `v002`처럼 버전과 비교 근거를 남긴다.
11. proof 원본은 사용자 소유·명시적 허가·검증 가능한 라이선스 중 하나여야 하며, 출처 URL·라이선스 URL·해시를 기록한다.
12. 기존 컷·자막·속도 변화·합성이 있는 영상은 새 편집 문법의 proof 원본으로 사용하지 않는다.
13. 자동 컷·프리즈 탐지는 후보 표시일 뿐이다. 주 에이전트가 원본 전체 시퀀스, plain, proof, 모든 전환 전후 프레임을 직접 보지 않은 결과는 검증 완료로 보고하지 않는다.
14. 촬영본에 필요한 행동·빛·표면·여백·거리별 커버리지가 없으면 자동 줌·프리즈·반복 프레임·무관한 효과로 채우지 않는다. 다른 문법, 단순 폴백, 재촬영 중 하나를 선택한다.
15. 한 컷 내부 편집을 검증하는 proof는 화면전환만으로 통과시키지 않는다. 행동·빛·초점·표면·시간·사진·영상·그래픽 중 하나가 원인과 결과를 가진 실제 내부 사건을 만들어야 한다.
16. AI가 기록할 수 있는 최고 상태는 `ready_for_user_review`다. 사용자의 명시적 `accepted` 전에는 스타일 완성·재현 성공·대표 프리셋 승인을 선언하지 않는다.
17. 사용자가 특정 안을 선택했거나 안 비교를 명시적으로 생략하지 않았다면 `safe`, `recommended`, `experimental` 세 안이 실제 응답과 treatment에 있어야 한다. 누락되면 편집·렌더를 시작하지 않는다.
18. 모든 신규 proof와 final edit는 schema `1.1`의 `timeline-grammar.json`을 만들고 narrative, shot, cut, timing, transition, text, color, audio, motion, purpose 10축을 정확한 시간 범위별로 채운다. CTA가 없으면 삭제하지 말고 `not_applicable`과 이유를 기록한다.
19. 음악은 에이전트가 생성하지 않는다. 기존 공개 무료 트랙 중 영상 동기화와 목표 게시 용도가 확인된 것만 사용하고 `audio-rights.json`과 `music-event-map.json`을 만든다. 권리 매니페스트가 없거나 검증에 실패하면 무음으로 돌아간다.
20. 편집 도구는 결과의 필요에 따라 선택하고 `toolchain`과 선택 이유를 기록한다. 프레임 정밀 컷·QC는 deterministic renderer, 내러티브 조립·색·마스터는 Resolve Edit/Color, 마스크·트래킹·화면 내부 합성은 Fusion, 라이선스 음원 믹싱은 Fairlight를 우선한다.
21. 공통 엔진이나 보조 스킬이 생성 beat track 또는 생성 음악을 제안해도 Haku 작업에서는 실행하지 않는다. 사용자가 오디오를 허용했지만 권리가 아직 확정되지 않았으면 `deferred_by_rights`로 유지한다.
22. schema `1.1` proof와 final edit는 `source-manifest.json`과 이벤트별 `source_mapping`을 가져야 한다. clip ID·경로·SHA-256·source in/out·source/output frame range가 없으면 렌더를 완료로 보고하지 않는다.
23. URL이나 로컬 영상의 첫 증거 수집에는 [watch-ingest-contract.md](references/watch-ingest-contract.md)를 적용한다. Windows에서는 작업공간의 `tools\run-watch.cmd`를 사용하고 권리 상태를 명시하며, 사용자 동의가 없으면 외부 음성 전사를 금지한다.
24. `/watch`가 추출한 프레임은 자동 분석 결과가 아니다. 주 에이전트가 나열된 프레임을 모두 직접 보고 [watch-evidence.template.json](references/watch-evidence.template.json)에 타임스탬프·관찰·추론·timeline event ID를 기록한 뒤 `scripts/validate_watch_evidence.py --check-files`를 통과시킨다.
25. 자연어 요청은 직접 원본 검토 뒤 [natural-language-request.template.json](references/natural-language-request.template.json)에 기록하고 `scripts/route_natural_language_request.py`로 라우팅한다. 라우터의 `needs_*` 상태를 효과 추가로 우회하지 말고, 누락 커버리지 재촬영·더 작은 Operator·단순 관찰 편집 중 하나를 선택한다.

## 모드 선택

- `analyze`: Reel 또는 사용자 촬영본의 연출·편집 특징을 추출
- `direct`: 콘셉트, 인물 동선, 미세 행동, 샷 리스트, 커버리지 설계
- `edit`: 컷 구조, 프리즈, 반복, 속도, 그래픽 매치 레시피 생성
- `grade`: 빛·색온도·계절감·질감 목표와 Resolve 노드 지시 생성
- `sound`: 원본 음악을 복사하지 않는 리듬·환경음·충격음 구조 생성
- `critique`: 결과물을 연출·촬영·편집·색·소리 문제로 분리 평가

여러 모드가 필요하면 `analyze → direct → edit → grade → sound → critique` 순서로 진행한다. 오디오가 범위 밖이면 `sound`를 생략하고 시각 편집만 비교한다.

## 자연어 요청 라우팅

1. 사용자의 원문을 축약하거나 스타일 이름으로 바꾸지 말고 request의 `natural_language`에 보존한다.
2. 권리와 기존 편집 여부를 먼저 판정하고, 주 에이전트가 원본 전체를 직접 본 뒤 실제로 촬영된 커버리지만 `material_observations.tags`에 기록한다.
3. `python scripts/route_natural_language_request.py REQUEST.json --output ROUTE.json`을 실행한다. 프로필은 [natural-language-routing-registry.json](references/natural-language-routing-registry.json), 작품 근거는 `auto-research-operator-registry.json`을 사용한다.
4. `ready_for_treatment_choice`일 때만 `safe`, `recommended`, `experimental`을 실제 treatment로 확장한다. 선택된 Operator의 10축 intent를 정확한 source/output frame의 `timeline-grammar.json`으로 구체화한다.
5. `needs_rights_verification`, `source_rejected_existing_edit`, `needs_source_review`, `needs_coverage_or_smaller_operator`, `no_semantic_match`는 렌더 허가가 아니다.
6. `python scripts/validate_natural_language_route.py ROUTE.json`을 통과시킨다. 라우터는 사용자 판정이나 승격 수치를 기록할 권한이 없다.

## 코퍼스 기준

40-Reel 분석이나 규칙 수정 작업에서는 [analysis-plan.md](references/analysis-plan.md)를 읽는다. 연출 태깅과 시퀀스 분석에서는 [directing-taxonomy.md](references/directing-taxonomy.md)를 읽고, 시간 구간별 편집 문법은 [timeline-grammar-dataset.md](references/timeline-grammar-dataset.md)와 [timeline-grammar-event.template.json](references/timeline-grammar-event.template.json)에 기록한다. 실제 연출·편집 설계 전에는 [archetypes.md](references/archetypes.md), [edit-grammar-registry.md](references/edit-grammar-registry.md), [operator-registry.md](references/operator-registry.md), [operator-registry.json](references/operator-registry.json), [auto-research-findings.md](references/auto-research-findings.md), [auto-research-operator-registry.json](references/auto-research-operator-registry.json), [natural-language-routing-registry.json](references/natural-language-routing-registry.json), [coverage-recipes.md](references/coverage-recipes.md)를 읽고, 두 인물 이상의 관계·추억형 Haku 편집을 설계할 때는 추가로 [relationship-sentence-coverage-gate.md](references/relationship-sentence-coverage-gate.md)를 읽는다. 현재 촬영본으로 성립하는 유형과 편집 문법만 선택한다. proof-cycle 작품 근거에서는 `auto-research-operator-registry.json`을 현재 권위로 사용하고, 자연어 결정론적 후보 검색에는 `natural-language-routing-registry.json`을 사용한다. `operator-registry.json`은 기존 이름·문법의 legacy catalog로만 사용한다. 새 40-Reel 직접 검토 결과와 기존 bootstrap 카드가 충돌하면 auto-research 자료를 우선한다. 손상되거나 인코딩이 깨진 카드로 라우팅하지 않는다. 다른 창작자 계정으로 스타일 라이브러리를 확장할 때는 [creator-expansion-roadmap.md](references/creator-expansion-roadmap.md)를 읽는다.

- 기존 10개를 가설 세트로 유지한다.
- 신규 30개를 검증 세트로 유지한다.
- 40개 전수 수치와 40개 전수 스토리보드를 모두 확인한다.
- `signature`, `supporting`, `special-device`, `coincidence`를 구분한다.
- 규칙의 빈도와 유형 간 반복을 함께 본다.

## 분석 워크플로

1. 원본 URL, 작성자, 날짜, 권리, 해시가 있는 매니페스트를 확인한다.
2. URL·로컬 영상의 초기 전수 탐색은 작업공간 `tools\run-watch.cmd -RightsStatus <status> "<source>" --detail balanced --out-dir <dir>`로 수행한다. 기본적으로 `--no-whisper`를 유지한다.
3. `/watch`가 나열한 모든 프레임을 직접 보고 `watch-evidence.json`을 만든다. 이 샘플링을 전체 재생·고밀도 타임라인 검토로 과장하지 않는다.
4. `scripts/collect_reference_reels.py`는 사용자가 요청한 공개 Reel만 개별 저장할 때 사용한다.
5. `scripts/analyze_corpus.py`로 컷·프리즈·암전·움직임·오디오·색·구도 지표와 스토리보드를 생성한다.
6. `scripts/build_storyboard_atlases.py`로 모든 Reel을 빠짐없이 시각 검토한다.
7. Reel 카드에 자동 측정과 시각 판정을 분리해 기록한다.
8. 2~8개 쇼트 묶음의 기능을 분석한다.
9. 빈도 기준을 통과한 규칙과 반례를 함께 정리한다.
10. 사용자 촬영본의 커버리지와 맞는 유형만 선택한다.

## Auto-research 루프

새 레퍼런스나 미검토 Reel이 들어오면 효과 이름부터 만들지 말고 다음 순서로 계속 연구한다.

1. 권리·계정·URL·날짜·해시를 확인하고 레퍼런스를 `public-reference-only`로 고정한다.
2. 전체 길이 스토리보드와 자동 컷·프리즈·암전 후보를 생성한다.
3. `scripts/build_dense_review_sheet.py`로 원본 비율을 보존한 dense timeline을 만든다. 컷이 0.25초보다 빠르면 8~12fps로 다시 만든다.
4. 주 에이전트가 storyboard와 dense timeline을 직접 본다. 자동 수치는 의미 판정에 사용하지 않고 재검토 위치만 표시한다.
5. 옆으로 저장된 영상은 회전 메타데이터·수평선·사람·건축의 중력 방향을 확인한다. 애매하면 시계·반시계 양방향 시트를 만들고 정상 방향을 직접 선택한다.
6. 검정 화면은 빈 화면, 작은 문장, chapter breath, 패널 release로 구분한다. 가는 적색 표시가 보이면 고밀도 시트로 문장인지 선인지 확인한다.
7. 전 구간 고정 표식은 워터마크 후보로 분리하고 Operator로 학습하지 않는다.
8. [semantic-review.template.json](references/semantic-review.template.json) 형식으로 작품 전체의 목적·연출·촬영·편집·소재 적합성·광고 기능·반례를 기록한다.
9. 의미 있는 변화마다 `timeline-grammar/<reel_id>.json` 이벤트를 만들고 narrative, shot, cut, timing, transition, text, color, audio, motion, purpose를 모두 기록한다. 효과명·사용 시점·적용 장면·사용 이유·시청자 느낌을 분리한다.
10. 오디오를 직접 검토하지 않았으면 beat, bass hit, sound anchor를 추정하지 않고 모든 오디오 세부값을 `not_reviewed`로 유지한다. 외부 무료 음원을 사용할 때는 [audio-source-and-rights-policy.md](references/audio-source-and-rights-policy.md)를 읽고 권리 검증 뒤에만 `licensed_library_track`으로 전환한다.
11. 관찰과 추론을 분리하고 최소 세 개의 정확한 시간 범위를 요구한다.
12. `scripts/validate_timeline_grammar.py`로 시간 범위·필수 축·목적 설명·오디오 보류를 검증한다.
13. `scripts/record_semantic_review.py`로 상태를 반영하고 `scripts/validate_research_state.py`로 전체 큐를 검증한다.
14. 서로 다른 작품 세 편 이상에서 같은 원인·결과 구조가 반복될 때만 corpus-supported 후보로 올린다.
15. 사용자 승인을 기다리며 연구를 멈추지 않는다. 다만 사용자가 직접 보지 않은 결과를 `accepted`로 추정하거나 기록하지 않는다.

`semantic_complete`는 직접 시각 검토가 끝났다는 뜻이지 사용자 승인을 뜻하지 않는다. 방향·실시간 운동·작은 문장·패널 타이밍이 애매하면 `needs_second_review`로 남긴다.

## 유형 선택 게이트

효과를 고르기 전에 아래 순서로 유형을 고른다.

1. 피사체가 사람, 사물, 풍경 중 무엇인지 판정한다.
2. 동일 행동의 ECU·CU·MS·WS가 있는지 확인한다.
3. 계절·물·빛·바람·그림자 같은 감각 인서트 수를 센다.
4. 한 장면을 오래 볼 만한 행동·구도·빛 변화가 있는지 확인한다.
5. 독자적인 문구·그래픽·분할 화면을 만들 근거가 있는지 확인한다.
6. 오디오가 범위에 있을 때만 사운드 프레이즈 또는 현장음으로 구조를 만들 수 있는지 확인한다.
7. `coverage-recipes.md`의 최소 커버리지를 충족한 유형만 후보로 남긴다.

후보가 여러 개면 가장 적은 가정과 재촬영으로 성립하는 유형을 고른다. 후보가 없으면 먼저 재촬영 목록을 만들고, 현재 촬영본으로는 `minimal-single-idea` 또는 독자적인 관찰형 편집만 제안한다.

마이크로컷은 기본값이 아니다. 40-Reel 검증에서 빠른 마이크로컷 그리드는 10개에서만 확인되었으므로 `sensory-flash-montage` 또는 명확한 상승 구간에서만 사용한다.

## 연출 설계

항상 다음을 분리해 지시한다.

- 첫 프레임과 첫 3초의 감각 훅
- 인물의 목표, 시선, 동선, 미세 행동
- 카메라 높이, 거리, 움직임, 흔들림 강도
- 전경·중경·배경과 음의 공간
- 빛의 방향, 시간대, 날씨, 물성
- 연결할 형태·색·방향·동작
- 반복 모티프와 마지막 잔상
- 각 행동의 시작·종료 핸들

사용자가 특정 연출안을 이미 선택했거나 안 비교를 명시적으로 생략하지 않은 한 `safe`, `recommended`, `experimental` 3개를 먼저 제시한다. 원본이 아직 없어도 한 가지 Haku 방향으로 곧바로 확정하지 않는다.

샷 리스트에는 `purpose`, `subject_action`, `camera`, `framing`, `light`, `motif`, `transition_pair`, `minimum_duration`, `repetitions`, `risk`, `fallback`을 넣는다.

## 편집 설계

`archetype`과 `edit grammar`를 분리한다. 유형은 소재·감정·사건을, 편집 문법은 쇼트의 시간·화면·행동 연결 방식을 결정한다. 결과물마다 `primary_edit_grammar` 하나와 선택적인 `secondary_operator` 하나만 고른다. 여러 문법을 같은 비중으로 섞지 않는다.

편집 레시피는 최소한 다음 레이어를 분리한다.

1. `macro_arc`: 도입·상승·정지·해방
2. `sequence_grammar`: 감각 훅·행동 분해·그래픽 브리지·모티프 반복
3. `micro_timing`: 컷 그리드·프리즈·암전·속도
4. `image_relation`: 형태·색·방향·물성·의미 연결
5. `sound_relation`: 온셋·프레이즈·현장음·침묵

각 레이어의 결정을 [timeline-grammar-dataset.md](references/timeline-grammar-dataset.md)의 schema `1.1`로 시간 구간별 저장한다. 필드 이름만 존재하는 빈 기록은 실패다. 전체 `narrative_arc`의 hook, setup, buildup, climax, resolution, CTA와 각 이벤트의 10축 값이 실제 화면·소리 근거를 가져야 한다.

연속된 모든 쇼트를 같은 속도로 자르지 않는다. 빠른 파편 앞뒤에 숨 쉴 구간을 둔다. 프리즈·역재생·줌은 의미가 있을 때만 사용한다.

오디오가 범위 밖이면 `sound_relation`을 생성하지 않는다. 이때 컷 타이밍을 임의의 비트에 맞추지 말고 화면 내부 행동·방향·형태·밝기 변화로 결정한다.

오디오가 범위에 들어오면 에이전트 생성 음악을 사용하지 않는다. [audio-rights.template.json](references/audio-rights.template.json), [music-event-map.template.json](references/music-event-map.template.json), [licensed-audio-recipe-block.template.json](references/licensed-audio-recipe-block.template.json)을 만들고 `scripts/validate_audio_rights.py --check-file`과 `scripts/validate_music_event_map.py --timeline-grammar`를 모두 통과시킨다. proof renderer는 같은 음원 파일·hash·source range·gain·fade를 plain/proof에 적용해야 한다. 모든 컷을 비트에 붙이지 말고 phrase, accent, break, drop, ending 중 화면 구조를 실제로 바꾸는 사건만 연결한다.

## 편집 도구 선택

- 단일 레이어 컷, 동일 프레임 수 plain/proof, 자동 QC: `ffmpeg` 기반 proof renderer
- 시퀀스 조립, 정밀 트림, compound clip, 최종 색보정과 마스터: DaVinci Resolve Edit/Color
- 사진·영상창·마스크·트래킹·선택적 움직임·한 컷 내부 그래픽: DaVinci Resolve Fusion
- 권리가 확인된 음원·환경음·효과음의 레벨·페이드·버스: Fairlight

Resolve나 Fusion을 썼다는 사실을 품질 증거로 간주하지 않는다. 프로젝트 경로, 사용 페이지, 노드·트랙 구조, 렌더 설정, 선택 이유를 `toolchain`과 레시피에 기록하고 원본·plain·proof 직접 비교로 판정한다.

자동 디지털 줌을 기본값으로 사용하지 않는다. 사용할 때는 시작·종료 배율을 기록하고 샷 경계에서 배율이 리셋되어 움찔하지 않는지 확인한다. 느린 재생은 정수 출력 프레임을 먼저 계산하고, 부족한 시간을 마지막 프레임 복제로 채우지 않는다.

40-Reel auto-research에서 확인된 다음 경계를 적용한다.

- 작은 적색 문장을 붉은 선 오버레이로 바꾸지 않는다. 독자적 카피가 읽히고 장·질문·명제·감정 punctuation 기능이 있을 때만 `meaningful-copy-gate`를 쓴다.
- 검정 여백을 균등 전환으로 반복하지 않는다. 실제 공간·기억 군집·카피 기능이 바뀔 때만 쓴다.
- 작은 영상 창은 환경·인물·행동·물성처럼 서로 다른 정보 역할이 있을 때만 쓴다. 동시에 크게 움직이는 창은 하나로 제한하고 뒤에 full-frame hero release를 둔다.
- 과노출·반사 relay는 실제 유리·물·역광·플레어가 촬영되었을 때만 쓴다. 일괄 노출 상승이나 밝기 펌핑으로 위조하지 않는다.
- 긴 저모션 숏은 자동 freeze 후보일 뿐이다. 인물·빛·물·바람의 미세 움직임과 장면 기능을 직접 확인한 뒤 유지·삭제를 판단한다.
- 한 컷 내부 사건, 행동 연속성, 관계 블로킹이 없는 원본은 마이크로컷과 전환으로 Haku처럼 보이게 만들 수 없다.

## 반복 비교 루프

완성본을 개선할 때는 효과를 계속 추가하지 말고 아래 루프를 반복한다.

1. `baseline`: 직전 버전과 선택 유형의 레퍼런스 5~8편을 고정한다.
2. `measure`: 길이·샷 수·샷 길이 분포·컷 밀도·프리즈 비율·밝기 변화와 스토리보드를 비교한다.
3. `diagnose`: 부족한 축을 `cut_density`, `image_relation`, `motif_transformation`, `micro_action`, `scale`, `color_time`, `ending`, `coverage`로 분리한다.
4. `limit`: 한 번의 버전에서는 원인 가설을 최대 4개만 수정한다.
5. `render`: 새 버전으로 렌더하고 레시피·검증·스토리보드를 함께 저장한다.
6. `reverse_compare`: 이전/새 버전의 동일 비율 시점과 모든 샷 중간 프레임을 나란히 본다.
7. `judge`: 가설마다 `pass`, `partial_pass`, `fail`과 화면 증거를 기록한다.
8. `next`: 남은 문제가 편집인지 촬영 커버리지인지 분리한 뒤 다음 버전의 수정 범위를 정한다.

샷 수가 레퍼런스 범위 안이면 더 자르는 것을 기본 해결책으로 삼지 않는다. 컷 수가 아니라 인접 화면의 형태·위치·방향·색·행동 관계와 반복 모티프의 변형을 먼저 고친다.

정량 지표가 좋아져도 스토리보드에서 관계가 읽히지 않으면 개선으로 판정하지 않는다. 반대로 프리즈 비율처럼 움직임 양이 그대로여도 이미지 관계와 감정 구조가 좋아졌다면 그 개선 축을 정확히 명시한다.

## 기술 fixture와 hero proof

새 편집 문법이나 연산자를 긴 영상에 섞기 전에 약 4초를 목표로 한 최소 증명 영상을 만든다. 4초는 강제 길이가 아니다. 준비·변화·결과가 읽히는 가장 짧은 길이를 사용하며 보통 3~8초, 필요한 경우에만 12초까지 허용한다.

이 결과는 `technical-fixture`다. 한 영상에는 기법 하나만 적용하고 같은 원본 구간의 `plain`과 `proof`를 만든다. 렌더 안정성은 검증하지만 Haku 스타일 대표성은 주장하지 않는다.

대표 결과는 별도의 8~20초 `hero-proof`로 만든다. 서사 여부와 관계없이 시각 전제, 감각·행동·빛·공간의 발전, 페이오프 또는 강한 마지막 이미지가 있어야 한다. 연출·영상미·편집 점수는 각각 8 이상, 계정 식별성과 광고 부합성은 각각 7 이상이어야 하며 사용자 `accepted` 전에는 승격하지 않는다.

라이선스가 확인된 무편집 원본을 새로 검증할 때는 다음 저자유도 경로를 사용한다.

1. `scripts/audit_raw_sources.py SOURCE_DIR --output-dir AUDIT_DIR --ffmpeg FFMPEG`로 전체 길이 스토리보드와 컷·정지·암전 후보를 만든다.
2. 주 에이전트가 각 원본 스토리보드를 직접 보고 `single_take`, `existing_edit_detected`, `haku_material_fit`, 제한 사항을 기록한다. [source-manifest.template.json](references/source-manifest.template.json)에 권리·파일 hash·capture world·숨은 retake 판정을 저장하고 `scripts/validate_source_manifest.py --check-files`를 통과시킨다.
3. 통과 원본만 JSON recipe의 `plain`과 `proof` 양쪽에 넣는다. material ID 집합, 절대 경로, 파일 해시, source anchor, 실제 사용 range·횟수를 각각 따로 기록한다. 같은 material ID 집합을 썼다는 사실을 같은 range·횟수를 썼다는 뜻으로 확장하지 않는다.
4. `scripts/render_proof_recipe.py RECIPE --output-dir OUTPUT --ffmpeg FFMPEG --ffprobe FFPROBE`로 동일 소스 세트 plain/proof, 비교 영상, 스토리보드, 모든 전환 strip, 자동 QC를 만든다.
   - 단일 레이어 컷만 필요할 때는 위 렌더러를 사용한다.
    - `memory-panel-poem`의 3분할, 역할 기반 비대칭 패널, 고정 위치의 순차 영상 창, 제한된 이전 영상 잔상, 의미 기능이 있는 카피처럼 화면 내부 동시 합성이 필요할 때는 `scripts/render_composite_proof_recipe.py`와 schema `1.1`을 사용한다. 허용 타입은 `single`, `fit-single`, `triptych`, `functional-panels`, `memory-window-reveal`, `bounded-video-trace`, `luminous-reflection-relay`, `copy-overlay`다. `luminous-reflection-relay`는 실제 창·유리·물·역광의 공통 광질과 인물의 실제 시선·몸 전환이 모두 있는 경우에만, 화면 전체에 screen blend를 0.12~0.42로 한 번 적용한다. recipe에는 `reflection_relation`으로 원본에 보이는 반사면·물리 표면·행동 촉발·광질 관계를 기록하고, 진입·이탈은 각각 0.20~1.00초의 부드러운 envelope로 적용한다. 이 증거가 없거나 서로 다른 빛·공간을 억지로 이어야 하면 렌더 전에 거절한다. 원본에 없는 반사·외부 세계·감정 행동을 위조하거나 일괄 노출 펌핑으로 대체하지 않는다. `fit-single`은 cover crop이 필수 행동·입퇴장·공간 관계·복수 인물을 삭제할 때만 원본 비율 전체를 보존하며, 남는 캔버스는 장식이나 약한 촬영본 은폐가 아니라 정보 보존 장치여야 한다. `functional-panels`는 환경·촉감·인물처럼 역할이 다른 2~4개 패널만 허용하고, `active_frames`로 한꺼번에 출현시키지 않고 원인 행동 뒤 밀도를 단계적으로 쌓을 수 있다. `copy-overlay`는 읽을 수 있는 1~3개 문장과 명시적 `active_frames`만 허용하며, plain/proof의 시간·소스·크롭·등급·움직임을 고정한 상태에서 카피의 의미 기능만 비교한다. plain/proof의 material ID 집합·절대 경로·hash·source anchor·실제 사용 range와 횟수를 별도 검사 결과로 기록한다.
   - `functional-panels`는 `common_anchor`(같은 인물·의상·장소·계절·행동 중 실제로 보이는 공통 세계)와 각 패널의 서로 다른 `role`을 명시해야 한다. 최소 하나는 뒤늦게 들어와야 하며, 모든 패널을 동시에 띄우는 범용 콜라주를 거절한다. 패널은 촉감·인물·공간·행동·거리처럼 겹치지 않는 정보 역할을 가져야 하고, 장이 바뀌면 black breath 또는 단일 이미지 release로 밀도를 풀어야 한다.
   - 각 functional panel은 최소 6프레임을 유지하고 기본 2~6프레임 alpha fade-in/out(또는 더 명시적인 값)을 거쳐야 한다. 두 fade 사이에 실제 hold가 남지 않으면 거절한다. 이는 패널이 한 프레임에 움찔하며 나타나거나 사라지는 것을 방지하는 기술 안전장치다.
   - 기능 패널의 원본 시간은 `active_frames`의 실제 등장 프레임부터 시작한다. 보이지 않는 동안 원본 시간을 미리 소모해서는 안 된다. 장 끝의 black breath는 `intentional_black_breath_frames: [start, end]`로 명시한 최종 1.5초 이하 구간만 허용하며, 모든 패널이 그 전까지 사라져야 한다. 자동 QC는 이 선언을 오류 대신 시각 검토 대상으로 남긴다. 선언되지 않은 연속 검은 프레임·정지 프레임은 계속 실패다.
5. `audio_policy`가 `deferred_by_user`이면 결과 영상은 무음이어야 한다. `licensed_library_track`이면 검증된 `audio-rights.json`과 `music-event-map.json`을 먼저 만들고 plain/proof에 동일 음원 파일·source range·gain curve를 사용한다.
   권리 확인이 끝나지 않았으면 `deferred_by_rights`로 기록하고 무음으로 렌더한다.
6. `max_threads`는 2 이하로 유지한다.
7. 주 에이전트가 원본→plain→proof→모든 transition strip 순서로 보고 `render-report.json`의 `visual_review`를 채운다. 화면 내부 패널·영상창·trace가 있으면 각 내부 사건의 시작·종료 전후 최소 5프레임 strip도 확인한다.
8. 라이브 전체 재생을 직접 확인하지 못했으면 그 제한을 공개하고 `full_playback_reviewed=false`로 둔다.
9. 사용자 판정은 `accepted`, `partial`, `rejected` 중 하나로 별도 기록한다. AI 사전검수만으로 규칙이나 Operator를 승격하지 않는다.

반복 연구에서는 `scripts/run_proof_cycle.py RECIPE --output-dir OUTPUT --ffmpeg FFMPEG --ffprobe FFPROBE`를 사용한다. 이 실행은 렌더 뒤 plain/proof 전체를 촘촘히 펼친 시트, 모든 샷 경계와 화면 내부 사건 전후 strip, 검토 manifest와 크리틱 초안을 만든다. 증거 생성은 직접 검토가 아니므로 자동으로 `pass`를 기록하지 않는다. 주 에이전트가 모든 이미지를 직접 본 뒤 `scripts/record_proof_review.py MANIFEST --research-verdict ...`로 화면 증거와 한계를 기록한다. 이 기록기는 이미 존재하는 사용자 판정과 승격 수치를 보존한다. 반복 상태는 [proof-cycle.template.json](references/proof-cycle.template.json) 형식을 따르고, tested Operator와 supporting Operator의 판정을 분리한다. `scripts/validate_proof_cycles.py --operator-registry auto-research-operator-registry.json --legacy-registry operator-registry.json`으로 등록된 Operator ID, 사용자 판정, 같은 tested Operator의 서로 다른 승인 상황 수를 검증한다. 전역 승인 수를 다른 Operator에 전용하지 않는다.

## 크리틱 기준

다음 질문을 순서대로 판정한다.

1. 첫 3초에 감각적 질문이 생기는가?
2. 인물·대상·공간 사이에 의미 관계가 있는가?
3. 쇼트 연결이 단순 교체가 아니라 형태·방향·행동을 이어 주는가?
4. 빠름과 느림, 움직임과 정지가 대비되는가?
5. 빛·색·물성이 같은 감정 세계를 만드는가?
6. 오디오가 범위에 있을 때, 소리가 컷을 장식하는 대신 이미지를 재해석하는가?
7. 마지막 이미지가 설명 없이 잔상을 남기는가?

문제를 `directing_gap`, `coverage_gap`, `edit_gap`, `grade_gap`, `sound_gap`, `reference_mismatch`로 분류한다.

## 출력 계약

가능한 범위에서 다음을 만든다.

- `reel-card.json`
- `timeline-grammar.json`
- `source-manifest.json` — proof에 사용한 무편집 원본의 권리·hash·capture world·single-take 판정
- `audio-rights.json` — 공개 무료 음원을 실제로 사용할 때
- `music-event-map.json` — 공개 무료 음원을 실제로 사용할 때
- `directing-concept.json`
- `shot-list.json`
- `coverage-plan.json`
- `edit-grammar-selection.json`
- `edit-recipe.json`
- `grade-plan.json`
- `sound-plan.json` — 오디오가 범위에 있을 때만
- `critique-report.json`
- `comparison-metrics.json`
- `comparison-before-after.md`
- `technique-proof-plain.mp4`
- `technique-proof.mp4`
- `technique-proof-storyboard.jpg`
- `technique-proof-explanation.md`
- `technique-proof-verdict.json`
- `hero-proof.json`
- `hero-proof-final.mp4`
- `hero-proof-storyboard.jpg`
- 버전별 스토리보드와 동일 비율 시점 비교 이미지

모든 결과에 선택한 유형, 적용 규칙, 제외한 규칙, 촬영본 한계, 증거 Reel을 기록한다.

## 완료 게이트

- 코퍼스 분석은 대상 Reel을 모두 확인했다.
- 규칙은 빈도 기준과 반례를 통과했다.
- 연출 지시가 편집 효과 목록보다 먼저 나온다.
- 사용자 촬영본으로 구현 불가능한 요소를 숨기지 않았다.
- 최종 결과물에 레퍼런스 미디어가 없다.
- 오디오가 범위에 있으면 소리 없는 검토와 소리 포함 검토를 모두 수행했고, 범위 밖이면 오디오 스트림이 없음을 확인했다.
- 컷·프리즈·움직임·색·감정 곡선을 따로 역검증했고, 오디오가 범위에 있을 때만 사운드도 역검증했다.
- 이전 버전과 새 버전을 스토리보드와 동일 비율 시점에서 역비교했다.
- 한 번의 버전에서 수정한 원인 가설은 4개 이하이고 각각 판정 근거가 있다.
- 모든 샷의 실제 프레임 수가 레시피와 일치하며 마지막 프레임 패딩이 없다.
- 연속 정지 구간이 샷 끝에 맞물리면 의도된 프리즈인지 렌더 패딩인지 판정하고, 패딩이면 실패 처리한다.
- 전환 전후 최소 5프레임을 나란히 확인해 모션 블러·배율 리셋·카메라 움찔이 없다.
- 선택한 유형의 최소 촬영 커버리지를 충족했고, 충족하지 못한 항목은 재촬영 또는 제한 사항으로 명시했다.
- 빠른 컷을 제거해도 행동·빛·공간·모티프 중 최소 두 축에서 연출 의도가 남는다.
- technical fixture를 스타일 대표 결과로 보고하지 않았다.
- hero proof는 연출·영상미·편집·계정 식별성·광고 부합성을 전체 재생으로 검증했다.
- 신규 proof 원본은 기존 편집이 없는 단일 테이크인지 주 에이전트가 전체 시퀀스로 확인했다.
- 원본·plain·proof·모든 전환 strip의 직접 시각 검수와 사용자 판정이 모두 기록되었다.
- 신규 proof와 final edit의 schema `1.1` `timeline-grammar.json`이 10축·전체 narrative arc·toolchain·원본 및 출력 frame mapping을 포함하고 `validate_timeline_grammar.py`를 통과했다.
- 신규 proof의 `source-manifest.json`이 실제 파일 hash·권리·capture world·single-take 판정을 포함하고 `validate_source_manifest.py --check-files`를 통과했다.
- 외부 음원을 사용했다면 생성 음악이 아니며 개별 트랙 페이지·라이선스·저작자·해시·표기 의무·Content ID 위험이 기록되고 `validate_audio_rights.py --check-file`과 `validate_music_event_map.py --timeline-grammar`를 통과했다.
- `/watch`를 사용했다면 명시적 권리 상태, 전사 정책, 모든 추출 프레임의 직접 검토, timeline event 연결이 `watch-evidence.json`에 있고 `validate_watch_evidence.py --check-files`를 통과했다.
