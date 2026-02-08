import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import calendar
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import json

# --- 1. 설정 및 구글 시트 연결 ---

# 로컬에서 쓸 파일 이름 (내 컴퓨터용)
JSON_FILE = 'family-ledger-486809-9594b880837a.json'
SPREADSHEET_NAME = '가계부데이터' 
HEADERS = ['날짜', '구분', '사용자', '카테고리', '내역', '금액']
COL_MAP = {'날짜': 1, '구분': 2, '사용자': 3, '카테고리': 4, '내역': 5, '금액': 6}

def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    try:
        # 1. 로컬(내 컴퓨터) 환경인지 확인
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    except FileNotFoundError:
        # 2. 파일이 없으면 배포(클라우드) 환경으로 간주하고 Secrets에서 키를 찾음
        # Streamlit Cloud에 배포할 때 이 부분으로 작동합니다.
        try:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        except Exception as e:
            st.error(f"로그인 정보(Secrets)를 찾을 수 없습니다: {e}")
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
        if not data:
            return pd.DataFrame(columns=HEADERS)
            
        df = pd.DataFrame(data)
        if '날짜' not in df.columns:
            return pd.DataFrame(columns=HEADERS)
        return df

    except Exception as e:
        return pd.DataFrame(columns=HEADERS)

def add_row(date, type_, user, category, item, amount):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    if not sheet.row_values(1):
        sheet.append_row(HEADERS)
    sheet.append_row([str(date), type_, user, category, item, int(amount)])

def delete_row(row_index):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    sheet.delete_rows(row_index + 2)

def update_cell(row_idx, col_name, new_value):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    sheet_row = row_idx + 2
    sheet_col = COL_MAP[col_name]
    if col_name == '금액':
        try:
            new_value = int(str(new_value).replace(',', ''))
        except:
            pass
    sheet.update_cell(sheet_row, sheet_col, new_value)

# --- 2. 메인 화면 ---
def main():
    st.set_page_config(page_title="우리집 가계부", layout="wide", page_icon="🏡")
    today = datetime.now()

    with st.sidebar:
        st.title("🏡 우리집 가계부")
        menu = st.radio("메뉴 이동", ["📝 입력 및 홈", "📅 달력 및 내역", "📊 맞춤형 분석"])
        st.markdown("---")
        target_budget = st.number_input("목표 생활비(원)", value=2000000, step=100000)

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

    # [탭 1] 입력 및 홈
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
            with st.form("input_form", clear_on_submit=True):
                date = st.date_input("날짜", today)
                exp_type = st.radio("구분", ["지출", "수입"], horizontal=True)
                user = st.selectbox("사용자", ["남편", "아내", "공용"])
                category = st.selectbox("카테고리", ["식비", "외식/배달", "쇼핑", "교통", "주거/통신", "의료/건강", "임신/육아", "저축", "기타"])
                item = st.text_input("내용")
                amount = st.number_input("금액", min_value=0, step=1000)
                
                if st.form_submit_button("저장하기"):
                    add_row(date, exp_type, user, category, item, amount)
                    st.success("저장되었습니다!")
                    time.sleep(0.5)
                    st.rerun()

        with col2:
            st.subheader("📋 최근 내역 (클릭해서 수정)")
            if not df.empty:
                edit_df = df.sort_values(by='날짜', ascending=False).head(15).copy()
                edit_df['날짜'] = edit_df['날짜'].dt.strftime('%Y-%m-%d')
                
                # [수정] use_container_width 경고 해결
                edited_data = st.data_editor(
                    edit_df,
                    use_container_width=True, # 최신 버전에서는 다시 이게 표준이 되기도 함 (경고가 계속 뜨면 width='stretch'로 변경)
                    num_rows="fixed",
                    hide_index=True,
                    column_config={
                        "금액": st.column_config.NumberColumn(format="%d원"),
                        "카테고리": st.column_config.SelectboxColumn(options=["식비", "외식/배달", "쇼핑", "교통", "주거/통신", "의료/건강", "임신/육아", "저축", "기타"]),
                        "사용자": st.column_config.SelectboxColumn(options=["남편", "아내", "공용"]),
                        "구분": st.column_config.SelectboxColumn(options=["지출", "수입"])
                    }
                )

                if st.button("수정사항 저장하기"):
                    if not edit_df.equals(edited_data):
                        with st.spinner("구글 시트에 수정사항 반영 중..."):
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

    # [탭 2] 달력 및 내역
    elif menu == "📅 달력 및 내역":
        col_cal, col_detail = st.columns([3, 2])

        with col_cal:
            st.header("📅 월별 달력")
            c1, c2 = st.columns(2)
            sel_year = c1.number_input("연도", value=today.year)
            sel_month = c2.number_input("월", value=today.month, min_value=1, max_value=12)
            
            calendar.setfirstweekday(calendar.SUNDAY)
            cal = calendar.monthcalendar(sel_year, sel_month)
            week_korean = ['일', '월', '화', '수', '목', '금', '토']
            
            cols = st.columns(7)
            for i, w in enumerate(week_korean):
                color = "red" if i == 0 else "blue" if i == 6 else "black"
                cols[i].markdown(f"<div style='text-align:center; color:{color}; font-weight:bold'>{w}</div>", unsafe_allow_html=True)
            
            if not df.empty:
                month_data = df[(df['날짜'].dt.year == sel_year) & (df['날짜'].dt.month == sel_month)]
            else:
                month_data = pd.DataFrame(columns=HEADERS)
            
            for week in cal:
                cols = st.columns(7)
                for i, day in enumerate(week):
                    if day == 0:
                        cols[i].write("")
                        continue
                    
                    bg_color = "transparent"
                    if i == 0: bg_color = "#FFF0F0"
                    elif i == 6: bg_color = "#F0F8FF"

                    content_html = f"""
                    <div style='background-color: {bg_color}; border-radius: 5px; padding: 5px; min-height: 80px; margin-bottom: 5px; font-size: 0.9em;'>
                        <div style='font-weight:bold; color:black;'>{day}</div>
                    """
                    
                    if not month_data.empty:
                        day_records = month_data[month_data['날짜'].dt.day == day]
                        if not day_records.empty:
                            d_exp = day_records[day_records['구분']=='지출']['금액'].sum()
                            d_inc = day_records[day_records['구분']=='수입']['금액'].sum()
                            
                            if d_exp > 0: content_html += f"<div style='color:red; font-weight:bold;'>-{d_exp:,.0f}</div>"
                            if d_inc > 0: content_html += f"<div style='color:blue; font-weight:bold;'>+{d_inc:,.0f}</div>"
                    
                    content_html += "</div>"
                    cols[i].markdown(content_html, unsafe_allow_html=True)

        with col_detail:
            st.header("🔍 일별 상세 내역")
            selected_date = st.date_input("확인할 날짜 선택", today)
            st.divider()
            
            if not df.empty:
                day_df = df[df['날짜'].dt.date == selected_date]
                if not day_df.empty:
                    d_income = day_df[day_df['구분']=='수입']['금액'].sum()
                    d_expense = day_df[day_df['구분']=='지출']['금액'].sum()
                    
                    st.markdown(f"### 📅 {selected_date.strftime('%Y년 %m월 %d일')}")
                    c1, c2 = st.columns(2)
                    c1.metric("총 수입", f"{d_income:,.0f}원")
                    c2.metric("총 지출", f"{d_expense:,.0f}원")
                    
                    st.markdown("#### 📝 사용 내역")
                    display_table = day_df[['사용자', '카테고리', '내역', '금액', '구분']].copy()
                    
                    # [수정] 경고 해결
                    st.dataframe(display_table.style.format({"금액": "{:,.0f}원"}), use_container_width=True, hide_index=True)
                else:
                    st.warning("기록된 내역이 없습니다.")
            else:
                st.warning("데이터가 없습니다.")

    # [탭 3] 맞춤형 분석
    elif menu == "📊 맞춤형 분석":
        st.header("📊 맞춤형 상세 분석")
        
        if df.empty:
            st.warning("분석할 데이터가 없습니다.")
        else:
            with st.expander("🔎 검색 조건 설정", expanded=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    default_start = today.replace(day=1)
                    date_range = st.date_input("기간 선택", (default_start, today))
                with col_f2:
                    all_cats = list(df['카테고리'].unique())
                    all_users = list(df['사용자'].unique())
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

                    tab_chart1, tab_chart2 = st.tabs(["차트 보기", "목록 보기"])
                    with tab_chart1:
                        exp_only = filtered_df[filtered_df['구분']=='지출']
                        if not exp_only.empty:
                            fig = px.pie(exp_only, values='금액', names='카테고리', hole=0.4)
                            # [수정] 경고 해결 (Plotly는 아직 use_container_width 사용)
                            st.plotly_chart(fig, use_container_width=True)
                    with tab_chart2:
                        # [수정] 경고 해결
                        st.dataframe(filtered_df.sort_values(by='날짜', ascending=False), use_container_width=True)
                else:
                    st.info("조건에 맞는 내역이 없습니다.")
            else:
                st.info("기간을 정확히 선택해주세요.")
                
            st.divider()
            with st.expander("🗑️ 데이터 삭제"):
                st.dataframe(df.sort_values(by='날짜', ascending=False).head(5)) 
                del_id = st.number_input("삭제할 행 번호", min_value=0, step=1)
                if st.button("삭제 실행"):
                    delete_row(del_id)
                    st.success("삭제되었습니다!")
                    st.rerun()

if __name__ == '__main__':
    main()