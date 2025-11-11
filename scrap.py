import os
import requests
import re
import time
import csv
from bs4 import BeautifulSoup, Comment

BASE_URL = "https://sdvx.in/sort/sort_{level}.htm"
SITE_DOMAIN = "https://sdvx.in"
TOTAL_LEVELS = 20

sort_pattern = re.compile(r'SORT(.*?)\(\);')

OUTPUT_CSV_FILE = "sdvxin_data.csv"

def main():
    print(f"총 {TOTAL_LEVELS}개 레벨의 데이터 수집을 시작합니다...")

    all_songs_data = []

    all_songs_data.append(["Name", "Level", "Link"])

    try:
        total_items_processed = 0

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
                        
                        all_songs_data.append([name, level_str, final_link])
                        
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
        
        try:
            with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(all_songs_data)
            print(f"성공적으로 총 {total_items_processed}개의 항목을 '{OUTPUT_CSV_FILE}' 파일에 저장했습니다.")
            
        except Exception as e_csv:
            print(f"  [오류] CSV 파일 저장 중 오류 발생: {e_csv}")

    except Exception as e_final:
        print(f"스크립트 실행 중 치명적인 오류가 발생했습니다: {e_final}")

if __name__ == "__main__":
    main()