# 공개 무료 음원 사용 정책

## 목적

Haku proof와 최종 편집에 필요한 음악은 에이전트가 생성하지 않는다. 기존에 공개된 음원 중 영상 동기화와 목표 게시 용도가 명시적으로 허용된 트랙만 내려받아 사용한다. 무료 다운로드라는 사실만으로 사용 권리를 추정하지 않는다.

## 허용 소스 우선순위

1. [Mixkit Stock Music](https://mixkit.co/free-stock-music/)
   - 공식 Stock Music Free License와 개별 트랙 페이지를 함께 저장한다.
   - Mixkit 안내상 YouTube, 소셜 플랫폼, 뮤직비디오, 팟캐스트, 웹사이트와 온라인 광고 용도에 사용할 수 있다.
   - CD·DVD·비디오게임·TV·라디오 사용은 기본 허용 범위가 아니므로 해당 목적에는 라우팅하지 않는다.
2. [Pixabay Music](https://pixabay.com/music/)
   - [Pixabay Content License](https://pixabay.com/service/license-summary/)와 개별 트랙 페이지를 함께 저장한다.
   - 영상이라는 더 큰 창작물에 포함해 수정·사용할 수 있지만 원본 음원을 standalone으로 배포하지 않는다.
   - Content ID 등록 여부를 기록하고, 등록 트랙이면 라이선스 인증서를 보관한다. Instagram·YouTube의 자동 감지 위험을 `content_id_status`에 남긴다.
3. [Free Music Archive](https://freemusicarchive.org/)
   - 개별 트랙 페이지의 실제 Creative Commons 라이선스를 확인한다.
   - 광고 가능성을 고려해 기본적으로 CC0 또는 CC BY만 허용한다.
   - ND는 영상과 음악의 동기화가 파생물에 해당하므로 거부한다. NC는 제품·서비스 홍보와 광고에 사용할 수 없으므로 거부한다. BY-SA도 결과물 라이선스 의무가 명확히 검토되지 않으면 거부한다.

## 필수 권리 기록

트랙마다 `audio-rights.json`에 다음을 저장한다.

- 제공처, 트랙명, 저작자
- 개별 트랙 페이지와 공식 라이선스 URL
- 다운로드 시각과 로컬 파일 SHA-256
- 사용 목적과 허용 근거
- 금지 용도
- 표기 의무와 실제 표기문
- Content ID 상태와 인증서 경로
- `generated_by_agent: false`

`scripts/validate_audio_rights.py AUDIO_RIGHTS --check-file`를 통과하지 못하면 타임라인에 넣지 않는다.

## 음악 선택과 편집

- 분위기 태그만으로 고르지 않는다. 필요한 `phrase_start`, `accent`, `break`, `drop`, `instrument_change`, `ending`을 먼저 정의한다.
- 선택 후 `music-event-map.json`에 정확한 트랙 타임코드, 화면 반응, 의도적 오프셋을 기록한다.
- 모든 컷을 비트에 붙이지 않는다. 중요한 음악 사건과 중요한 화면 사건만 연결한다.
- 음소거 상태에서도 narrative와 행동 인과가 읽혀야 한다.
- plain/proof에서 음악을 검증할 때는 같은 파일·같은 source range·같은 gain curve를 사용한다.
- 원본 Haku Reel의 음악과 사운드를 복사하지 않는다.
- 렌더·ZIP·저장소에서 음원을 독립 파일로 재배포하지 않는다.

## 실패 처리

다음 중 하나면 음악을 사용하지 않고 `deferred_by_rights` 또는 무음 proof로 돌아간다.

- 개별 트랙 페이지 또는 공식 라이선스 URL이 없음
- 영상 동기화 허용 여부가 불명확함
- 광고 목적과 NC 조건이 충돌함
- ND 조건임
- 로컬 파일 해시가 권리 매니페스트와 다름
- Content ID 위험을 사용자 제출물에서 설명할 수 없음
- 음악이 화면 사건을 강화하지 않고 약한 편집을 가림
