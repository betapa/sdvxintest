import os
import requests # requests는 이미 상단에 import 되어 있습니다.
import re
import time
from bs4 import BeautifulSoup, Comment
from notion_client import Client
from notion_client.errors import APIResponseError

# --- 1. 설정 ---
# (이 부분은 변경 없음)
BASE_URL = "https://sdvx.in/sort/sort_{level}.htm"
SITE_DOMAIN = "https://sdvx.in"
TOTAL_LEVELS = 20
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID")
PROP_NAME = "Name"
PROP_LEVEL = "Level"
PROP_LINK = "Link"
sort_pattern = re.compile(r'SORT(.*?)\(\);')


# --- 2. Notion 갱신/생성 함수 (수정됨) ---

def update_notion_page(notion, name, level, link):
    """
    [수정됨] Notion DB를 조회하여 'Link'가 없으면 새 페이지를 생성, 있으면 갱신합니다.
    문제가 되는 notion.databases.query() 대신 requests를 사용하여 API를 직접 호출합니다.
    """
    
    # 디버깅 코드는 유지
    print(f"  [Debug] 함수 진입: Name='{name}', Level='{level}', Link='{link}'")

    try:
        # --- [수정 시작] ---
        # 1. 'notion.databases.query()' 대신 'requests'로 API 직접 호출
        
        print(f"  [Debug] '{name}'의 DB 쿼리 실행 (requests 직접 호출)...")
        
        query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        
        # Notion API 헤더 설정
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28", # 안정적인 API 버전 명시
            "Content-Type": "application/json"
        }
        
        # 쿼리 필터 설정
        query_payload = {
            "filter": {
                "property": PROP_LINK,
                "url": {
                    "equals": link
                }
            }
        }
        
        # API 요청
        response = requests.post(query_url, headers=headers, json=query_payload)
        response.raise_for_status() # 오류 발생 시 예외 처리
        query_response = response.json()
        
        # --- [수정 끝] ---
        
        print(f"  [Debug] '{name}'의 query 실행 성공. (결과 {len(query_response.get('results', []))}개)")

        # 2. Notion API에 전송할 데이터 포맷 정의 (변경 없음)
        properties_data = {
            PROP_NAME: {"title": [{"text": {"content": name}}]},
            PROP_LEVEL: {"rich_text": [{"text": {"content": level}}]},
            PROP_LINK: {"url": link}
        }

        # 3. 결과에 따라 생성 또는 갱신 (페이지 생성/수정은 notion_client 객체 그대로 사용)
        if query_response.get("results"):
            # [갱신]
            page_id = query_response["results"][0]["id"]
            notion.pages.update(page_id=page_id, properties=properties_data)
            print(f"  [갱신] {name} (Lv: {level})")
        else:
            # [생성]
            notion.pages.create(
                parent={"database_id": DATABASE_ID},
                properties=properties_data
            )
            print(f"  [생성] {name} (Lv: {level})")

        # Notion API 속도 제한 (초당 평균 3회)을 준수하기 위해 대기
        time.sleep(0.5)

    except APIResponseError as e:
        print(f"  [Notion API 오류] {name} (Lv: {level}) 처리 중 오류 발생: {e}")
    except requests.exceptions.RequestException as e_req: # requests 오류 처리 추가
        print(f"  [Requests 오류] {name} (Lv: {level}) 쿼리 중 오류 발생: {e_req}")
    except Exception as e:
        print(f"  [Debug] 오류 발생. 전달된 값: Name='{name}', Level='{level}'")
        print(f"  [Notion 기타 오류] {name} (Lv: {level}) 처리 중 오류 발생: {e}")

# --- 3. 메인 스크래핑 및 실행 로직 ---
# (이 부분은 변경 없음)
def main():
    print(f"총 {TOTAL_LEVELS}개 레벨의 데이터 수집 및 Notion 갱신을 시작합니다...")

    if not NOTION_API_KEY or not DATABASE_ID:
        print("오류: NOTION_API_KEY 또는 DATABASE_ID가 GitHub Secrets에 설정되지 않았습니다.")
        print("스크립트를 종료합니다.")
        return

    try:
        # [최종 진단] 코드는 이제 삭제해도 됩니다.
        
        # client_instance 변수명 사용 (이전 제안 반영)
        client_instance = Client(auth=NOTION_API_KEY)
        total_items_processed = 0

        # 1부터 20까지 (TOTAL_LEVELS) 루프
        for i in range(1, TOTAL_LEVELS + 1):
            level_str = f"{i:02d}"
            URL = BASE_URL.format(level=level_str)
            
            print(f"\n--- [Level {level_str}] 페이지 처리 중 (URL: {URL}) ---")

            try:
                # 1. HTML 다운로드
                response = requests.get(URL)
                response.raise_for_status()
                response.encoding = 'utf-8' 
                html_content = response.text

                # 2. BeautifulSoup 파싱
                soup = BeautifulSoup(html_content, 'html.parser')
                script_tags = soup.find_all('script', src=lambda s: s and s.endswith('sort.js'))
                
                page_item_count = 0

                # 3. 페이지 내 항목 파싱 (제공된 로직 활용)
                for tag in script_tags:
                    try:
                        # Part 1 (폴더 경로)
                        src_path = tag.get('src') 
                        if not src_path:
                            continue
                        
                        split_path = src_path.split('/')
                        if len(split_path) < 2:
                            continue 
                        
                        part1 = split_path[1] # '03'
                        
                        # Part 2 (파일 이름)
                        next_script_tag = tag.find_next_sibling('script')
                        if not next_script_tag or not next_script_tag.string:
                            continue
                        
                        script_content = next_script_tag.string.strip()
                        match = sort_pattern.search(script_content)
                        if not match:
                            continue
                            
                        part2_upper = match.group(1) # '03075U'
                        part2_lower = part2_upper.lower() # '03075u'

                        # Name (이름)
                        comment = next_script_tag.find_next_sibling(string=lambda t: isinstance(t, Comment))
                        if not comment:
                            continue
                        
                        name = comment.strip()

                        # 최종 URL 조합
                        final_link = f"{SITE_DOMAIN}/{part1}/{part2_lower}.htm"
                        
                        # 4. CSV 저장 대신 Notion DB 업데이트 함수 호출
                        update_notion_page(client_instance, name, level_str, final_link)
                        page_item_count += 1
                        total_items_processed += 1

                    except Exception as e_item:
                        print(f"  [경고] {level_str}레벨의 특정 항목 파싱 중 오류 발생: {e_item} (항목 건너뜀)")
                
                print(f"-> Level {level_str}에서 {page_item_count}개의 항목을 처리했습니다.")

                # 서버 부담을 줄이기 위해 각 *페이지* 요청 사이에 1초 대기
                time.sleep(1)

            except requests.exceptions.RequestException as e_page:
                print(f"  [오류] {URL} 페이지를 가져오는 데 실패했습니다: {e_page} (Level 건너뜀)")
            except Exception as e_parse:
                print(f"  [오류] {URL} 페이지 파싱 중 알 수 없는 오류 발생: {e_parse} (Level 건너뜀)")

        print("\n--- 모든 페이지 처리 완료 ---")
        print(f"성공적으로 총 {total_items_processed}개의 항목을 Notion DB에서 처리/갱신했습니다.")

    except ImportError:
        print("오류: 'requests', 'beautifulsoup4', 'notion-client' 라이브러리가 설치되지 않았습니다.")
        print("requirements.txt에 이 라이브러리들을 추가해주세요.")
    except Exception as e_final:
        print(f"스크립트 실행 중 치명적인 오류가 발생했습니다: {e_final}")

if __name__ == "__main__":
    main()