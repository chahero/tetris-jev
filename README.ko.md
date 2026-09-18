# Tetris / Jev

[English](README.md)

**같은 테트리스, 서로 다른 판단 방식.** TypeSafe Jev가 블록을 놓는 위치를
선택하는 모습을, API 없이 동작하는 규칙 기반 플레이와 비교합니다.

## 플레이 영상

| Jev API 모드 | 오프라인 규칙 모드 |
| --- | --- |
| [![Jev 자동 플레이](media/jev-preview.gif)](media/jev.mp4) | [![오프라인 자동 플레이](media/offline-preview.gif)](media/offline.mp4) |
| [전체 영상 1분 15초](media/jev.mp4) · [스크린샷](media/jev.png) | [전체 영상 29초](media/offline.mp4) · [스크린샷](media/offline.png) |

두 영상은 **시드 42, 최대 60개 블록, 애니메이션 2배속**으로 직접 실행해
녹화했습니다. Jev 응답을 기다리는 시간도 포함되므로 영상 길이는 다릅니다.
GIF는 실제 영상의 8초 발췌본이며 추가 배속 편집은 하지 않았습니다.
영상이 바로 재생되지 않으면 파일 페이지의 View raw 또는 Download를 이용하세요.

| 결과 | Jev | 오프라인 |
| --- | ---: | ---: |
| 배치한 블록 | 60개 | 60개 |
| 제거한 줄 | 22줄 | 22줄 |
| 점수 | 3,800점 | 3,700점 |
| 최종 높이 / 빈 구멍 | 3칸 / 1개 | 3칸 / 1개 |
| API 호출 | 60회 | 없음 |

둘 다 게임오버 없이 블록 수 제한에 도달했습니다. 줄 제거 시점과 묶음에 따라
레벨별 점수가 달라집니다. **한 시드의 데모 결과이므로 Jev의 일반적인 우위를
증명하는 벤치마크는 아닙니다.** 다시 실행하면 모델 선택과 응답 시간이 달라질 수 있습니다.

## 어떻게 다른가요?

- **Jev**: 현재 보드와 가능한 배치별 높이·구멍·굴곡·제거할 줄 수를 전달합니다.
  모델이 회전과 열을 선택하면 코드가 낙하 애니메이션과 실제 배치를 수행합니다.
  가능한 배치를 규칙으로 미리 순위 매기거나 추려서 전달하지 않습니다.
- **오프라인**: 줄 제거에 가점, 높이·구멍·굴곡에 감점을 주는 고정 계산식으로 선택합니다.
  API 키와 비용이 필요 없으며 모델 확률을 만들어 표시하지 않습니다.
- 추론을 기다리는 동안 게임은 멈춥니다. 네트워크 지연 때문에 블록을 놓치지 않습니다.
- 반복 플레이가 모델 자체를 학습시키지는 않습니다.

표준 규칙 전체를 구현한 테트리스는 아닙니다. 10×20 보드, 7-bag 블록 생성,
수직 낙하 배치를 사용하며 홀드·벽차기·끼워넣기·T-spin·실시간 중력은 없습니다.

## 실행

Python 3.13 이상과 uv를 준비합니다. 영상 녹화에는 FFmpeg도 필요합니다.

```powershell
git clone https://github.com/chahero/tetris-jev.git
cd tetris-jev
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
Copy-Item .env.example .env # 첫 설정에만 실행하세요.
```

`.env`에 `TYPESAFE_API_KEY=실제키`를 입력한 뒤 실행합니다.

- `play.cmd`: Jev API 자동 플레이
- `play-offline.cmd`: API 없는 자동 플레이
- Space: 일시정지·재개, R: 같은 시드로 재시작, +/-: 속도 순환, Esc: 종료
- 기본 한도는 한 판 200개 블록입니다. `--max-pieces 60`으로 변경할 수 있습니다.
- `--paused`를 붙이면 API를 호출하지 않고 일시정지 상태로 창을 엽니다.

## 영상 녹화

```powershell
.\.venv\Scripts\tetris-jev.exe --policy jev --seed 42 --max-pieces 60 --speed 2 --exit-after --record media\jev.mp4
.\.venv\Scripts\tetris-jev.exe --policy heuristic --seed 42 --max-pieces 60 --speed 2 --exit-after --record media\offline.mp4
```

지정된 영상 파일이 이미 있으면 덮어씁니다. 게임 내부 화면만 녹화하며
다른 창이나 API 키 파일은 포함하지 않습니다. 요청 실패 시 자동으로 멈추며
오프라인 정책으로 몰래 대체하지 않습니다.

실행 로그는 `artifacts/`에 저장합니다. `.env`·가상환경·원본 로그는 Git에서
제외하고, README에서 사용하는 영상·GIF·스크린샷만 `media/`에 포함합니다.
비공개 저장소를 다른 사람에게 보여주려면 해당 사람에게 저장소 접근 권한이 필요합니다.
