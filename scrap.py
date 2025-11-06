import os
import requests
import re
import time
from bs4 import BeautifulSoup, Comment
from notion_client import Client
from notion_client.errors import APIResponseError

# --- [최종 진단 코드] ---
# 스크립트가 임포트한 'notion_client' 모듈의 실제 파일 위치를 출력합니다.
try:
    import notion_client
    print(f"\n[최종 진단] 임포트된 'notion_client' 모듈의 실제 파일 경로:")
    print(f"-> {notion_client.__file__}\n")
except Exception as e:
    print(f"\n[최종 진단] 'notion_client' 임포트 실패: {e}\n")
# -------------------------


# --- 1. 설정 --- (이하 동일)
BASE_URL = "https://sdvx.in/sort/sort_{level}.htm"
SITE_DOMAIN = "https://sdvx.in"
TOTAL_LEVELS = 20 # 1부터 20까지
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID")
PROP_NAME = "Name"
PROP_LEVEL = "Level"
PROP_LINK = "Link"
sort_pattern = re.compile(r'SORT(.*?)\(\);')

# --- 2. Notion 갱신/생성 함수 ---
def update_notion_page(notion, name, level, link):
    """
    Notion DB를 조회하여 'Link'가 없으면 새 페이지를 생성, 있으면 갱신합니다.
    """
    
    # [디버깅] 함수가 올바른 인수로 호출되었는지 확인
    print(f"  [Debug] 함수 진입: Name='{name}', Level='{level}', Link='{link}'")

    try:
        # 1. 'Link' 속성을 기준으로 DB에 데이터가 있는지 조회
        print(f"  [Debug] '{name}'의 notion.databases.query 실행 직전...")
        query_response = notion.databases.query(
            database_id=DATABASE_ID,
            filter={
                "property": PROP_LINK,
                "url": {
                    "equals": link
                }
            }
        )
        print(f"  [Debug] '{name}'의 query 실행 성공. (결과 {len(query_response['results'])}개)")

        # 2. Notion API에 전송할 데이터 포맷 정의
        properties_data = {
            PROP_NAME: {"title": [{"text": {"content": name}}]},
            PROP_LEVEL: {"rich_text": [{"text": {"content": level}}]}, 
            PROP_LINK: {"url": link}
        }

        # 3. 결과에 따라 생성 또는 갱신
        if query_response["results"]:
            page_id = query_response["results"][0]["id"]
            notion.pages.update(page_id=page_id, properties=properties_data)
            print(f"  [갱신] {name} (Lv: {level})")
        else:
            notion.pages.create(
                parent={"database_id": DATABASE_ID},
                properties=properties_data
            )
            print(f"  [생성] {name} (Lv: {level})")

        time.sleep(0.5)

    except APIResponseError as e:
        print(f"  [Notion API 오류] {name} (Lv: {level}) 처리 중 오류 발생: {e}")
    except Exception as e:
        print(f"  [Debug] 오류 발생. 전달된 값: Name='{name}', Level='{level}'")
        print(f"  [Notion 기타 오류] {name} (Lv: {level}) 처리 중 오류 발생: {e}")

# --- 3. 메인 스크래핑 및 실행 로직 ---
def main():
    print(f"총 {TOTAL_LEVELS}개 레벨의 데이터 수집 및 Notion 갱신을 시작합니다...")

    if not NOTION_API_KEY or not DATABASE_ID:
        print("오류: NOTION_API_KEY 또는 DATABASE_ID가 GitHub Secrets에 설정되지 않았습니다.")
        print("스크립트를 종료합니다.")
        return

    try:
        notion_client = Client(auth=NOTION_API_KEY)
        total_items_processed = 0

        # 1부터 20까지 (TOTAL_LEVELS) 루프
        for i in range(1, TOTAL_LEVELS + 1):
            level_str = f"{i:02d}"
            URL = BASE_URL.format(level=level_str)
            
            print(f"\n--- [Level {level_str}] 페이지 처리 중 (URL: {URL}) ---")

            try:
                response = requests.get(URL)
                response.raise_for_status()
                response.encoding = 'utf-8'
                html_content = response.text

                soup = BeautifulSoup(html_content, 'html.parser')
                script_tags = soup.find_all('script', src=lambda s: s and s.endswith('sort.js'))
                
                page_item_count = 0

                for tag in script_tags:
                    try:
                        src_path = tag.get('src') 
                        if not src_path:
                            continue
                        
                        split_path = src_path.split('/')
                        if len(split_path) < 2:
                            continue
                        part1 = split_path[1] 
                        
                        next_script_tag = tag.find_next_sibling('script')
                        if not next_script_tag or not next_script_tag.string:
                            continue
                        
                        script_content = next_script_tag.string.strip()
                        match = sort_pattern.search(script_content)
                        if not match:
                            continue
                        part2_upper = match.group(1)
                        part2_lower = part2_upper.lower()

                        comment = next_script_tag.find_next_sibling(string=lambda t: isinstance(t, Comment))
                        if not comment:
                            continue
                        name = comment.strip()

                        final_link = f"{SITE_DOMAIN}/{part1}/{part2_lower}.htm"
                        
                        update_notion_page(notion_client, name, level_str, final_link)
                        page_item_count += 1
                        total_items_processed += 1

                    except Exception as e_item:
                        print(f"  [경고] {level_str}레벨의 특정 항목 파싱 중 오류 발생: {e_item} (항목 건너뜀)")
                
                print(f"-> Level {level_str}에서 {page_item_count}개의 항목을 처리했습니다.")
                time.sleep(1)

            except requests.exceptions.RequestException as e_page:
                print(f"  [오류] {URL} 페이지를 가져오는 데 실패했습니다: {e_page} (Level 건너뜀)")
            except Exception as e_parse:
                print(f"  [오류] {URL} 페이지 파싱 중 알 수 없는 오류 발생: {e_parse} (Level 건너뜀)")

        print("\n--- 모든 페이지 처리 완료 ---")
        print(f"성공적으로 총 {total_items_processed}개의 항목을 Notion DB에서 처리/갱신했습니다.")

    except ImportError:
        print("오류: 'requests', 'beautifulsoup4', 'notion-client' 라이브러리가 설치되지 않았습니다.")
    except Exception as e_final:
        print(f"스크립트 실행 중 치명적인 오류가 발생했습니다: {e_final}")

if __name__ == "__main__":
    main()