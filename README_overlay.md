# HTML Overlay (Windows)

테두리 없는(always-on-top) HTML 오버레이 창 실행기입니다.

## 설치

```powershell
pip install -r requirements.txt
```

## 실행

기본(`2048.html`) 실행:

```powershell
python html_overlay.py
```

원하는 HTML 파일 또는 URL로 실행:

```powershell
python html_overlay.py "C:\path\to\addon.html"
python html_overlay.py "https://example.com/overlay"
```

이전 옵션도 계속 사용 가능:

```powershell
python html_overlay.py --html "C:\path\to\addon.html"
```

또는 `run_overlay.bat` 실행.

## 조작

- 항상 위: 기본 적용
- 이동: 창 안에서 `좌클릭 드래그`
- 크기 조절: 창 가장자리/모서리에서 `좌클릭 드래그`
- 우클릭 메뉴: `Open HTML File...`, `Open URL...`, `Opacity`, `Scale`, `Click-Through`, `Exit`
- 클릭 통과 ON: 창 아래 프로그램과 상호작용 가능

## 참고

- 클릭 통과 ON 상태에서는 창 자체 클릭이 막히므로, 시스템 트레이 아이콘 우클릭 메뉴에서도 클릭 통과를 OFF로 되돌릴 수 있습니다.
- Windows 전용 구현(`pywin32`)입니다.
