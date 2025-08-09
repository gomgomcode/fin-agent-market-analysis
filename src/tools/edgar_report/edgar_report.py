import requests
import re
import time
import random
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_result,
)
from pydantic import BaseModel, ConfigDict, Field
import sec_edgar_api


class EdgarReporterWrapper(BaseModel):
    """SEC EDGAR 10-K/10-Q report analyzer with comprehensive company lookup"""
    
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )
    
    edgar_client: Optional[sec_edgar_api.EdgarClient] = Field(default=None, exclude=True)
    user_agent: str = Field(default="Pseudo-lab/gomgomcode@gmail.com")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialize_edgar_client()
    
    def _initialize_edgar_client(self):
        """SEC EDGAR API 클라이언트 초기화"""
        try:
            self.edgar_client = sec_edgar_api.EdgarClient(user_agent=self.user_agent)
        except Exception as e:
            print(f"EDGAR 클라이언트 초기화 실패: {e}")
            self.edgar_client = None
    
    def clean_company_name(self, company_name: str) -> str:
        """회사명에서 법인 형태 접미사를 제거하는 함수"""
        suffixes = [
            r'\binc\.?$', r'\bincorporated$', r'\bcorp\.?$', r'\bcorporation$',
            r'\bllc$', r'\bllp$', r'\blimited$', r'\bltd\.?$', r'\bco\.?$',
            r'\bcompany$', r'\bgroup$', r'\bholdings?$', r'\benterprise$',
            r'\bsolutions$', r'\btechnologies$', r'\bservices$', r'\bsystems$'
        ]
        
        cleaned_name = company_name.lower().strip()
        
        for suffix in suffixes:
            cleaned_name = re.sub(suffix, '', cleaned_name, flags=re.IGNORECASE).strip()
        
        # 연속된 공백을 하나로 합치기
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name)
        
        return cleaned_name
    
    def find_company_cik(self, company_name: str) -> Optional[Dict[str, str]]:
        """회사명으로부터 CIK와 티커를 찾는 함수"""
        try:
            # SEC의 회사 검색 API 사용
            search_url = "https://www.sec.gov/files/company_tickers.json"
            headers = {'User-Agent': self.user_agent}
            
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                companies_data = response.json()
                
                # 검색어 정리
                company_name_lower = company_name.lower()
                cleaned_search_name = self.clean_company_name(company_name)
                
                # 1단계: 정확한 일치 확인 (원본 검색어)
                for key, company_info in companies_data.items():
                    company_title = company_info['title'].lower()
                    ticker = company_info['ticker'].lower()
                    cik = str(company_info['cik_str']).zfill(10)
                    
                    if (company_name_lower == company_title or 
                        company_name_lower == ticker):
                        
                        return {
                            'cik': cik,
                            'ticker': company_info['ticker'],
                            'company_name': company_info['title']
                        }
                
                # 2단계: 정리된 회사명으로 정확한 일치 확인
                for key, company_info in companies_data.items():
                    company_title = company_info['title']
                    ticker = company_info['ticker'].lower()
                    cleaned_company_title = self.clean_company_name(company_title)
                    cik = str(company_info['cik_str']).zfill(10)
                    
                    if (cleaned_search_name == cleaned_company_title or 
                        company_name_lower == ticker):
                        
                        return {
                            'cik': cik,
                            'ticker': company_info['ticker'],
                            'company_name': company_info['title']
                        }
                
                # 3단계: 부분 일치 검색
                for key, company_info in companies_data.items():
                    company_title = company_info['title']
                    cleaned_company_title = self.clean_company_name(company_title)
                    cik = str(company_info['cik_str']).zfill(10)
                    
                    if (cleaned_search_name in cleaned_company_title or 
                        cleaned_company_title in cleaned_search_name):
                        
                        return {
                            'cik': cik,
                            'ticker': company_info['ticker'],
                            'company_name': company_info['title']
                        }
                
                # 4단계: 유사한 회사들 찾기
                similar_companies = []
                search_words = [word for word in cleaned_search_name.split() if len(word) > 2]
                
                if search_words:
                    for key, company_info in companies_data.items():
                        company_title = company_info['title']
                        cleaned_company_title = self.clean_company_name(company_title)
                        
                        if all(word in cleaned_company_title for word in search_words):
                            similar_companies.append({
                                'cik': str(company_info['cik_str']).zfill(10),
                                'ticker': company_info['ticker'],
                                'company_name': company_info['title']
                            })
                    
                    if similar_companies:
                        return similar_companies[0]
                        
            return None
            
        except Exception as e:
            print(f"회사 검색 중 오류: {e}")
            return None
    
    @retry(
        retry=(retry_if_result(lambda x: x.status_code == 429 if hasattr(x, 'status_code') else False)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
    )
    def make_request(self, url: str) -> requests.Response:
        """Make a request with retry logic for rate limiting"""
        time.sleep(random.uniform(1, 3))
        response = requests.get(url, headers={'User-Agent': self.user_agent}, timeout=30)
        return response
    
    def get_company_filings(self, company_identifier: str) -> Optional[Dict[str, Any]]:
        """회사 식별자로부터 회사 정보와 파일링을 가져오는 함수"""
        if not self.edgar_client:
            return None
            
        company_info = None
        
        # CIK가 숫자인지 확인
        if company_identifier.replace('-', '').isdigit():
            cik = company_identifier.replace('-', '').zfill(10)
            company_info = {'cik': cik}
        else:
            # 회사명 또는 티커로 CIK 찾기
            company_info = self.find_company_cik(company_identifier)
            
            if not company_info:
                return None
        
        try:
            # SEC EDGAR API로 회사 정보 가져오기
            cik = company_info['cik']
            submissions = self.edgar_client.get_submissions(cik=cik)
            
            # 최근 파일링들 확인
            recent_filings = submissions['filings']['recent']
            
            return {
                'company_info': submissions,
                'recent_filings': recent_filings,
                'cik': cik
            }
            
        except Exception as e:
            print(f"회사 정보 조회 중 오류: {e}")
            return None
    
    def get_10k_document_content(self, cik: str, accession_number: str) -> Optional[str]:
        """10-K 문서 내용을 가져오는 함수"""
        try:
            accession_clean = accession_number.replace('-', '')
            base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}"
            
            # 가능한 파일명들
            possible_filenames = [
                f"{accession_number}.txt",
                "form10k.htm",
                f"{accession_number}-10-k.htm"
            ]
            
            for filename in possible_filenames:
                filing_url = f"{base_url}/{filename}"
                
                try:
                    response = self.make_request(filing_url)
                    
                    if response.status_code == 200:
                        return response.text
                        
                except Exception as e:
                    continue
            
            return None
            
        except Exception as e:
            print(f"10-K 문서 조회 중 오류: {e}")
            return None
    
    def extract_business_section(self, document_content: str) -> str:
        """10-K 문서에서 Business 섹션을 추출"""
        try:
            # Item 1. Business 섹션 찾기
            business_start = document_content.find("ITEM 1. BUSINESS")
            if business_start == -1:
                business_start = document_content.find("Item 1. Business")
            if business_start == -1:
                business_start = document_content.find("ITEM 1.\nBUSINESS")
                
            if business_start != -1:
                # Item 2까지의 내용 추출
                item2_start = document_content.find("ITEM 2.", business_start)
                if item2_start == -1:
                    item2_start = document_content.find("Item 2.", business_start)
                
                if item2_start != -1:
                    business_section = document_content[business_start:item2_start]
                else:
                    business_section = document_content[business_start:business_start+10000]  # 처음 10000자
                
                return business_section
            
            return "Business 섹션을 찾을 수 없습니다."
            
        except Exception as e:
            return f"Business 섹션 추출 중 오류: {e}"
    
    def analyze_company_report(self, company_identifier: str, report_type: str = "10-K") -> str:
        """회사의 SEC 보고서를 분석하여 포맷된 결과 반환"""
        try:
            # 회사 파일링 정보 가져오기
            filing_data = self.get_company_filings(company_identifier)
            
            if not filing_data:
                return f"❌ '{company_identifier}'에 대한 회사 정보를 찾을 수 없습니다."
            
            company_info = filing_data['company_info']
            recent_filings = filing_data['recent_filings']
            cik = filing_data['cik']
            
            # 보고서 타입에 맞는 파일링 필터링
            form_types = recent_filings['form']
            filing_dates = recent_filings['filingDate']
            accession_numbers = recent_filings['accessionNumber']
            
            target_filings = []
            for i, form in enumerate(form_types):
                if form == report_type:
                    target_filings.append({
                        'form': form,
                        'filingDate': filing_dates[i],
                        'accessionNumber': accession_numbers[i]
                    })
            
            if not target_filings:
                return f"❌ '{company_info['name']}'의 {report_type} 파일링을 찾을 수 없습니다."
            
            # 결과 포맷팅
            result = f"📊 **SEC {report_type} 보고서 분석** - {company_info['name']}\n\n"
            
            # 회사 기본 정보
            result += f"### 🏢 회사 정보\n"
            result += f"• **회사명**: {company_info['name']}\n"
            result += f"• **CIK**: {company_info['cik']}\n"
            result += f"• **티커**: {', '.join(company_info.get('tickers', ['N/A']))}\n"
            result += f"• **SIC 코드**: {company_info.get('sic', 'N/A')}\n"
            result += f"• **업종**: {company_info.get('sicDescription', 'N/A')}\n"
            result += f"• **설립 주**: {company_info.get('stateOfIncorporation', 'N/A')}\n\n"
            
            # 파일링 정보
            result += f"### 📋 최근 {report_type} 파일링 ({len(target_filings)}건)\n"
            
            for i, filing in enumerate(target_filings[:5]):  # 최대 5개만 표시
                result += f"**{i+1}. {filing['filingDate']}**\n"
                result += f"   • Accession Number: {filing['accessionNumber']}\n"
                
                # 최신 10-K의 Business 섹션 추출
                if i == 0 and report_type == "10-K":
                    document_content = self.get_10k_document_content(cik, filing['accessionNumber'])
                    if document_content:
                        business_section = self.extract_business_section(document_content)
                        if business_section and len(business_section) > 100:
                            # Business 섹션 요약 (처음 1500자)
                            business_preview = business_section[:1500].replace('\n', ' ').strip()
                            result += f"   • **Business 섹션 미리보기**: {business_preview}...\n"
                
                result += "\n"
            
            # 분석 링크 제공
            latest_filing = target_filings[0]
            edgar_link = f"https://www.sec.gov/edgar/browse/?CIK={cik}"
            result += f"### 🔗 추가 정보\n"
            result += f"• **SEC EDGAR 페이지**: {edgar_link}\n"
            result += f"• **최신 파일링 날짜**: {latest_filing['filingDate']}\n"
            result += f"• **분석된 보고서 타입**: {report_type}\n"
            
            return result
            
        except Exception as e:
            return f"❌ SEC 보고서 분석 중 오류 발생: {str(e)}"