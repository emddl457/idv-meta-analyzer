import os

file_path = "main.py" 

with open(file_path, 'r', encoding='utf-8') as file:
    code = file.read()

# alignment 속성을 Flet 1.0 최신 문법(대문자)으로 일괄 변경
code = code.replace("ft.alignment.center", "ft.Alignment.CENTER")
code = code.replace("ft.alignment.top_left", "ft.Alignment.TOP_LEFT")
code = code.replace("ft.alignment.top_right", "ft.Alignment.TOP_RIGHT")
code = code.replace("ft.alignment.bottom_left", "ft.Alignment.BOTTOM_LEFT")
code = code.replace("ft.alignment.bottom_right", "ft.Alignment.BOTTOM_RIGHT")

with open(file_path, 'w', encoding='utf-8') as file:
    file.write(code)

print("✅ 성공적으로 ft.alignment 가 ft.Alignment 로 변경되었습니다!")