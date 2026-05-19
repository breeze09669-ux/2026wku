# pyrefly: ignore [missing-import]
from bs4 import BeautifulSoup as bs
from selenium import webdriver as wb
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import os
from urllib.request import urlretrieve
import json

# =======================================================
# 1. 수집하고 싶은 네이버 플레이스 '메뉴' 탭 URL을 입력하세요.
# 주의: /home 대신 /menu/list 가 붙은 URL을 사용하면 가장 좋습니다.
# =======================================================
url = 'https://m.place.naver.com/restaurant/1726715456/menu/list'

print("🚀 브라우저를 엽니다...")
driver = wb.Chrome()
driver.get(url)
time.sleep(3) # 페이지 로딩 대기

# =======================================================
# 2. 스크롤 및 '더보기' 버튼 클릭 (동적 데이터 로딩)
# =======================================================
print("⬇️ 스크롤을 내려 모든 메뉴를 로딩합니다...")
body = driver.find_element(By.TAG_NAME, 'body')

# 스크롤 10번 진행 (메뉴가 많으면 숫자를 늘리세요)
for num in range(10): 
    body.send_keys(Keys.PAGE_DOWN)
    time.sleep(0.5)
    
# 네이버 플레이스의 '더보기' 버튼을 찾아서 모두 클릭
try:
    more_btns = driver.find_elements(By.XPATH, "//*[contains(text(), '더보기') or contains(text(), '메뉴 더보기')]")
    for btn in more_btns:
        btn.click()
        time.sleep(1)
except Exception as e:
    pass # 더보기 버튼이 없으면 무시

# =======================================================
# 3. 데이터 파싱 (뷰티풀수프)
# =======================================================
print("🔍 메뉴 데이터를 추출합니다...")
soup = bs(driver.page_source, 'lxml')

# 네이버 플레이스는 클래스명이 복잡하므로 메뉴가 담긴 전체 리스트(ul, li 또는 a 태그)를 넓게 잡습니다.
menu_items = soup.find_all('a', href=lambda href: href and 'order' in href.lower() or 'menu' in href.lower())
if not menu_items:
    # a 태그로 못 찾으면 li 태그로 다시 시도
    menu_items = soup.find_all('li')

menu_data = []

# 이미지 저장 폴더 생성
save_dir = './menu_images'
os.makedirs(save_dir, exist_ok=True)

for item in menu_items:
    text = item.text.strip()
    
    # 텍스트에 '원'이 포함되어 있으면 메뉴로 간주
    if '원' in text and len(text) > 3:
        # 메뉴 이름 추출 (일반적으로 span이나 div의 첫 번째 텍스트)
        name_tag = item.find('span')
        if not name_tag:
            name_tag = item.find('div')
            
        menu_name = name_tag.text.strip() if name_tag else text.split('원')[0].strip()
        
        # 가격 추출
        price_tag = item.find('em')
        menu_price = price_tag.text.strip() + "원" if price_tag else ""
        if not menu_price:
            # em 태그가 없으면 텍스트에서 '원' 주변 글자를 유추
            import re
            price_match = re.search(r'([0-9,]+원)', text)
            menu_price = price_match.group(1) if price_match else ""

        # 이미지 추출 (img 태그)
        img_url = ""
        img_tag = item.find('img')
        if img_tag and 'src' in img_tag.attrs:
            img_url = img_tag['src']
            if not img_url.startswith('http'):
                img_url = ""
                
        # 중복 방지 (이미 추가된 메뉴인지 이름으로 확인)
        if menu_name and not any(m['name'] == menu_name for m in menu_data):
            menu_data.append({
                'name': menu_name,
                'price': menu_price,
                'img_url': img_url
            })

# =======================================================
# 4. 이미지 다운로드 및 JSON 저장
# =======================================================
print(f"\n✅ 총 {len(menu_data)}개의 메뉴를 찾았습니다. 이미지 다운로드를 시작합니다...")
file_no = 1

for menu in menu_data:
    print(f"[{file_no}] 메뉴명: {menu['name']} | 가격: {menu['price']}")
    
    if menu['img_url']:
        try:
            # 특수문자 제거하여 파일명 안전하게 생성
            safe_name = "".join([c for c in menu['name'] if c.isalnum() or c in (' ', '_')]).rstrip()
            file_path = f'{save_dir}/{file_no}_{safe_name}.jpg'
            
            urlretrieve(menu['img_url'], file_path)
            # 다운로드 성공 시, JSON 데이터의 이미지 경로를 로컬 경로로 업데이트!
            menu['local_image_path'] = file_path
            print(f"   => 📸 사진 저장 완료: {file_path}")
        except Exception as e:
            print(f"   => ❌ 사진 저장 실패: {e}")
            menu['local_image_path'] = ""
    else:
        print("   => 🚫 사진 없음")
        menu['local_image_path'] = ""
        
    file_no += 1
    time.sleep(0.5) # 서버 과부하 방지용 딜레이

# =======================================================
# 5. 앱에 자동 적용되도록 auto_import.js 생성
# =======================================================
app_menus = []
for m in menu_data:
    app_menus.append({
        "name": m['name'],
        "desc": { "ko": "", "en": "" },
        "price": m['price'],
        "image": m['local_image_path'] if m['local_image_path'] else ""
    })

# 자바스크립트 파일로 덮어쓰기 (메뉴 리스트만 전달)
js_content = f"window.AUTO_IMPORT_MENUS = {json.dumps(app_menus, ensure_ascii=False, indent=2)};"
with open('auto_import.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print(f"\n🎉 모든 작업이 완료되었습니다!")
print(f"사진들은 '{save_dir}' 폴더에 저장되었으며, 앱에 등록할 준비가 되었습니다.")
print(f"이제 브라우저에서 'index.html'을 새로고침하신 후, 원하시는 식당의 [수정(Edit)] 버튼을 누르시고")
print(f"[파이썬 메뉴 불러오기] 버튼을 클릭하시면 방금 수집한 메뉴와 사진이 해당 식당에 쏙 들어갑니다!")

driver.quit()
