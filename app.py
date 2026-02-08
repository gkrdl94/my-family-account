import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import calendar
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. 설정 및 구글 시트 연결 ---

JSON_FILE = 'family-ledger-486809-9594b880837a.json'
SPREADSHEET_NAME = '가계부데이터' 
HEADERS = ['날짜', '구분', '사용자', '카테고리', '내역', '금액']
FIXED_HEADERS = ['일자', '구분', '사용자', '카테고리', '내역', '금액']

COL_MAP = {'날짜': 1, '구분': 2, '사용자': 3, '카테고리': 4, '내역': 5, '금액': 6}

INCOME_CATS = ["월급", "월세", "성과급", "부수입", "기타"]
EXPENSE_CATS = ["외식/배달", "공과금", "식비", "쇼핑", "교통", "의료/건강", "임신/육아", "생필품", "여행", "취미", "축의/조의", "주거", "통신", "자동차", "미용", "용돈", "저축", "기타"]

def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        # 로컬 환경
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    except FileNotFoundError:
        # 클라우드 환경
        try:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        except:
            return None
    client = gspread.authorize(creds)
    return client

def get_data():
    try:
        client = get_client()
        if not client: return pd.DataFrame(columns=HEADERS)
        sheet = client.open(SPREADSHEET_NAME).sheet1
        
        first_row = sheet.row_values(1)
        if not first_row or first_row != HEADERS:
            sheet.insert_row(HEADERS, index=1)
            return pd.DataFrame(columns=HEADERS)

        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=HEADERS)
        df = pd.DataFrame(data)
        if '날짜' not in df.columns: return pd.DataFrame(columns=HEADERS)
        return df
    except:
        return pd.DataFrame(columns=HEADERS)

def get_fixed_data():
    try:
        client = get_client()
        if not client: return pd.DataFrame(columns=FIXED_HEADERS)
        try:
            sheet = client.open(SPREADSHEET_NAME).worksheet("고정지출")
        except:
            sheet = client.open(SPREADSHEET_NAME).add_worksheet(title="고정지출", rows=100, cols=10)
            sheet.append_row(FIXED_HEADERS)
            return pd.DataFrame(columns=FIXED_HEADERS)

        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=FIXED_HEADERS)
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=FIXED_HEADERS)

def add_row(date, type_, user, category, item, amount):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    if not sheet.row_values(1): sheet.append_row(HEADERS)
    sheet.append_row([str(date), type_, user, category, item, int(amount)])

def add_fixed_row(day, type_, user, category, item, amount):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).worksheet("고정지출")
    if not sheet.row_values(1): sheet.append_row(FIXED_HEADERS)
    sheet.append_row([int(day), type_, user, category, item, int(amount)])

def delete_row(row_index):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    sheet.delete_rows(row_index + 2)

def delete_fixed_row(row_index):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).worksheet("고정지출")
    sheet.delete_rows(row_index + 2)

def update_cell(row_idx, col_name, new_value):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    sheet_row = row_idx + 2
    sheet_col = COL_MAP[col_name]
    if col_name == '금액':
        try: new_value = int(str(new_value).replace(',', ''))
        except: pass
    sheet.update_cell(sheet_row, sheet_col, new_value)

# --- 2. 메인 화면 ---
def main():
    st.set_page_config(page_title="우리집 가계부", layout="wide", page_icon="🏡")
    today = datetime.now()

    # CSS 스타일
    st.markdown("""
    <style>
    .calendar-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 2px;
        margin-bottom: 20px;
    }
    .day-header {
        text-align: center;
        font-weight: bold;
        font-size: 0.8em;
        padding: 5px 0;
    }
    .day-cell {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 4px;
        min-height: 50px;
        font-size: 0.7em;
        position: relative;
    }
    @media (max-width: 600px) {
        .day-cell { min-height: 45px; font-size: 0.65em; }
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🏡 우리집 가계부")
        menu = st.radio("메뉴 이동", ["📝 입력 및 홈", "🔄 고정 지출 관리", "📅 달력", "📊 분석"])
        st.markdown("---")
        target_budget = st.number_input("목표 생활비(원)", value=2000000, step=100000, format="%d")

    # 데이터 로딩
    df = get_data()
    if not df.empty:
        try:
            if df['금액'].dtype == object:
                df['금액'] = df['금액'].astype(str).str.replace(',', '').astype(float).astype(int)
            else:
                df['금액'] = pd.to_numeric(df['금액'])
            df['날짜'] = pd.to_datetime(df['날짜'])
        except:
            df = pd.DataFrame(columns=HEADERS)

    # ==========================
    # [탭 1] 입력 및 홈
    # ==========================
    if menu == "📝 입력 및 홈":
        st.header(f"{today.month}월 가계부 현황")
        
        if not df.empty:
            this_month_df = df[(df['날짜'].dt.month == today.month) & (df['날짜'].dt.year == today.year)]
            total_expense = this_month_df[this_month_df['구분']=='지출']['금액'].sum()
        else:
            total_expense = 0

        if target_budget > 0:
            percent = min(total_expense / target_budget, 1.0)
            st.markdown(f"**목표 달성률 ({percent*100:.1f}%)**")
            st.progress(percent)
            st.caption(f"목표 {target_budget:,.0f}원 중 **{total_expense:,.0f}원** 사용")

        st.divider()
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("✍️ 내역 입력")
            exp_type = st.radio("구분", ["지출", "수입"], horizontal=True, key="main_radio")
            
            if exp_type == "수입":
                cat_options = INCOME_CATS
            else:
                cat_options = EXPENSE_CATS

            with st.form("input_form", clear_on_submit=True):
                date = st.date_input("날짜", today)
                user = st.selectbox("사용자", ["해기", "에디", "같이"])
                category = st.selectbox("카테고리", cat_options)
                item = st.text_input("내용")
                amount = st.number_input("금액", min_value=0, step=1000)
                
                if st.form_submit_button("저장하기"):
                    add_row(date, exp_type, user, category, item, amount)
                    st.success("저장되었습니다!")
                    time.sleep(0.5)
                    st.rerun()

        with col2:
            st.subheader("📋 최근 내역 (클릭해서 수정)")
            
            # [핵심] 버튼을 담을 빈 공간(Placeholder)을 미리 만듭니다.
            # 코드는 순서대로 실행되지만, 이 공간에 나중에 버튼을 채워넣으면 화면상으로는 위에 뜹니다.
            button_placeholder = st.empty()
            
            if not df.empty:
                edit_df = df.sort_values(by='날짜', ascending=False).head(20).copy()
                edit_df['날짜'] = edit_df['날짜'].dt.strftime('%Y-%m-%d')
                edit_df = edit_df[['날짜', '구분', '금액', '카테고리', '내역', '사용자']]
                all_cats = list(set(INCOME_CATS + EXPENSE_CATS))

                # 표 높이 자동 계산
                dynamic_height = (len(edit_df) + 1) * 35 + 3

                # 데이터 에디터 그리기 (화면상 아래에 위치)
                edited_data = st.data_editor(
                    edit_df,
                    use_container_width=True,
                    height=dynamic_height,
                    num_rows="fixed",
                    hide_index=True,
                    column_config={
                        "금액": st.column_config.NumberColumn(format="%d원"),
                        "카테고리": st.column_config.SelectboxColumn(options=all_cats),
                        "사용자": st.column_config.SelectboxColumn(options=["해기", "에디", "같이"]),
                        "구분": st.column_config.SelectboxColumn(options=["지출", "수입"])
                    }
                )

                # [핵심] 아까 만들어둔 위쪽 빈 공간에 '저장 버튼'을 집어넣습니다.
                with button_placeholder:
                    # type="primary"로 버튼을 빨갛게 강조합니다.
                    if st.button("💾 수정사항 저장하기 (수정 후 클릭)", type="primary", use_container_width=True):
                        if not edit_df.equals(edited_data):
                            with st.spinner("구글 시트에 저장 중..."):
                                for index, row in edited_data.iterrows():
                                    original_row = edit_df.loc[index]
                                    for col in HEADERS:
                                        if str(row[col]) != str(original_row[col]):
                                            update_cell(index, col, row[col])
                                st.success("수정이 완료되었습니다!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.info("변경된 내용이 없습니다.")
            else:
                st.info("데이터가 없습니다.")

    # ==========================
    # [탭 2] 고정 지출 관리
    # ==========================
    elif menu == "🔄 고정 지출 관리":
        st.header("🔄 매월 고정 지출/수입 설정")
        
        fixed_df = get_fixed_data()

        with st.expander("➕ 새 고정 항목 추가하기", expanded=True):
            f_type = st.radio("구분", ["지출", "수입"], horizontal=True, key="fixed_radio")
            f_cats = INCOME_CATS if f_type == "수입" else EXPENSE_CATS

            with st.form("fixed_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                day = c1.number_input("매월 며칠?", min_value=1, max_value=31, value=1)
                amount = c2.number_input("금액", min_value=0, step=10000)
                
                c3, c4 = st.columns(2)
                user = c3.selectbox("사용자", ["해기", "에디", "같이"])
                category = c4.selectbox("카테고리", f_cats)
                item = st.text_input("내용 (예: 월세)")
                
                if st.form_submit_button("리스트에 추가"):
                    add_fixed_row(day, f_type, user, category, item, amount)
                    st.success("추가되었습니다!")
                    time.sleep(0.5)
                    st.rerun()

        st.divider()

        st.subheader("🚀 이번 달 가계부에 적용하기")
        if not fixed_df.empty:
            st.dataframe(fixed_df.style.format({"금액": "{:,.0f}원"}), use_container_width=True)
            
            if st.button("📅 이번 달 내역으로 일괄 등록하기", type="primary"):
                count = 0
                for index, row in fixed_df.iterrows():
                    try:
                        target_day = int(row['일자'])
                        last_day = calendar.monthrange(today.year, today.month)[1]
                        if target_day > last_day: target_day = last_day
                        target_date = today.replace(day=target_day).strftime('%Y-%m-%d')
                        add_row(target_date, row['구분'], row['사용자'], row['카테고리'], row['내역'], row['금액'])
                        count += 1
                    except Exception as e:
                        st.error(f"에러: {e}")
                st.success(f"총 {count}건 등록 완료!")
                time.sleep(1)
                st.rerun()
            
            st.markdown("---")
            st.subheader("🗑️ 고정 항목 삭제")
            del_idx = st.number_input("삭제할 행 번호 (위 표의 왼쪽 숫자)", min_value=0, step=1)
            if st.button("선택한 항목 영구 삭제"):
                delete_fixed_row(del_idx)
                st.warning("삭제되었습니다.")
                st.rerun()
        else:
            st.info("등록된 고정 지출이 없습니다.")

    # ==========================
    # [탭 3] 달력
    # ==========================
    elif menu == "📅 달력":
        st.header("📅 월별 달력")
        c1, c2 = st.columns(2)
        sel_year = c1.number_input("연도", value=today.year)
        sel_month = c2.number_input("월", value=today.month, min_value=1, max_value=12)
        
        calendar.setfirstweekday(calendar.SUNDAY)
        cal = calendar.monthcalendar(sel_year, sel_month)
        week_korean = ['일', '월', '화', '수', '목', '금', '토']
        
        header_html = '<div class="calendar-container">'
        for i, w in enumerate(week_korean):
            color = "red" if i == 0 else "blue" if i == 6 else "black"
            header_html += f'<div class="day-header" style="color:{color}">{w}</div>'
        header_html += '</div>'
        st.markdown(header_html, unsafe_allow_html=True)

        if not df.empty:
            month_data = df[(df['날짜'].dt.year == sel_year) & (df['날짜'].dt.month == sel_month)]
        else:
            month_data = pd.DataFrame(columns=HEADERS)

        grid_html = '<div class="calendar-container">'
        for week in cal:
            for i, day in enumerate(week):
                if day == 0:
                    grid_html += '<div class="day-cell" style="border:none;"></div>'
                    continue
                
                bg_color = "transparent"
                if i == 0: bg_color = "#FFF0F0"
                elif i == 6: bg_color = "#F0F8FF"
                
                cell_content = f'<div style="font-weight:bold;">{day}</div>'
                
                if not month_data.empty:
                    day_records = month_data[month_data['날짜'].dt.day == day]
                    if not day_records.empty:
                        d_exp = day_records[day_records['구분']=='지출']['금액'].sum()
                        d_inc = day_records[day_records['구분']=='수입']['금액'].sum()
                        
                        if d_exp > 0:
                            cell_content += f'<div style="color:red; font-size:0.85em;" class="amount-text">-{d_exp:,.0f}</div>'
                        if d_inc > 0:
                            cell_content += f'<div style="color:blue; font-size:0.85em;" class="amount-text">+{d_inc:,.0f}</div>'
                
                grid_html += f'<div class="day-cell" style="background-color:{bg_color};">{cell_content}</div>'
        grid_html += '</div>'
        st.markdown(grid_html, unsafe_allow_html=True)

        st.divider()
        st.header("🔍 일별 상세 내역")
        selected_date = st.date_input("확인할 날짜 선택", today)
        
        if not df.empty:
            day_df = df[df['날짜'].dt.date == selected_date]
            if not day_df.empty:
                d_income = day_df[day_df['구분']=='수입']['금액'].sum()
                d_expense = day_df[day_df['구분']=='지출']['금액'].sum()
                
                m1, m2 = st.columns(2)
                m1.metric("수입", f"{d_income:,.0f}원")
                m2.metric("지출", f"{d_expense:,.0f}원")
                
                display_table = day_df[['구분', '금액', '카테고리', '내역', '사용자']].copy()
                st.dataframe(display_table.style.format({"금액": "{:,.0f}원"}), use_container_width=True, hide_index=True)
            else:
                st.info("해당 날짜의 내역이 없습니다.")

    # ==========================
    # [탭 4] 맞춤형 분석
    # ==========================
    elif menu == "📊 분석":
        st.header("📊 맞춤형 상세 분석")
        
        if df.empty:
            st.warning("데이터가 없습니다.")
        else:
            with st.expander("🔎 검색 조건", expanded=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    default_start = today.replace(day=1)
                    date_range = st.date_input("기간", (default_start, today))
                with col_f2:
                    all_users = list(df['사용자'].unique())
                    all_cats = list(set(INCOME_CATS + EXPENSE_CATS))
                    selected_cats = st.multiselect("카테고리", all_cats, default=all_cats)
                    selected_users = st.multiselect("사용자", all_users, default=all_users)

            if len(date_range) == 2:
                start_date, end_date = date_range
                mask = (
                    (df['날짜'].dt.date >= start_date) & 
                    (df['날짜'].dt.date <= end_date) & 
                    (df['카테고리'].isin(selected_cats)) &
                    (df['사용자'].isin(selected_users))
                )
                filtered_df = df.loc[mask]

                if not filtered_df.empty:
                    total_inc = filtered_df[filtered_df['구분']=='수입']['금액'].sum()
                    total_exp = filtered_df[filtered_df['구분']=='지출']['금액'].sum()
                    
                    st.divider()
                    m1, m2 = st.columns(2)
                    m1.metric("기간 수입", f"{total_inc:,.0f}원")
                    m2.metric("기간 지출", f"{total_exp:,.0f}원")

                    display_filtered = filtered_df[['날짜', '구분', '금액', '카테고리', '내역', '사용자']].sort_values(by='날짜', ascending=False)
                    st.dataframe(display_filtered.style.format({"금액": "{:,.0f}원"}), use_container_width=True)
                else:
                    st.info("내역이 없습니다.")
            else:
                st.info("기간을 선택해주세요.")
                
            st.divider()
            with st.expander("🗑️ 데이터 삭제"):
                st.dataframe(df.sort_values(by='날짜', ascending=False).head(5).style.format({"금액": "{:,.0f}원"})) 
                del_id = st.number_input("삭제할 행 번호", min_value=0, step=1)
                if st.button("삭제 실행"):
                    delete_row(del_id)
                    st.success("삭제되었습니다!")
                    st.rerun()

if __name__ == '__main__':
    main()
