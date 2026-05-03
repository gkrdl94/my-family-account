import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import calendar
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import os

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
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    except FileNotFoundError:
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

# --- [NEW] 여러 줄 삭제 지원 함수 ---
def delete_multiple_rows(indices_to_delete):
    client = get_client()
    sheet = client.open(SPREADSHEET_NAME).sheet1
    
    # 구글 시트는 여러 행을 한 번에 지우는 batch 삭제가 비효율적이거나 어려울 때가 있으므로
    # 인덱스가 꼬이지 않도록 역순으로 정렬해서 삭제합니다.
    sorted_indices = sorted(indices_to_delete, reverse=True)
    for idx in sorted_indices:
        sheet.delete_rows(idx + 2)

# --- 팝업(Dialog) 기능 정의 ---
@st.dialog("상세 내역 확인")
def popup_details(df_to_show, title):
    st.markdown(f"#### {title}")
    if not df_to_show.empty:
        show_df = df_to_show[['구분', '금액', '카테고리', '내역', '사용자']].copy()
        st.dataframe(show_df.style.format({"금액": "{:,.0f}원"}), use_container_width=True, hide_index=True)
        
        exp_sum = df_to_show[df_to_show['구분']=='지출']['금액'].sum()
        inc_sum = df_to_show[df_to_show['구분']=='수입']['금액'].sum()
        c1, c2 = st.columns(2)
        c1.metric("지출 합계", f"{exp_sum:,.0f}원")
        c2.metric("수입 합계", f"{inc_sum:,.0f}원")
    else:
        st.info("해당 내역이 없습니다.")

# --- 로그인 및 화면 꾸미기 ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔒 우리집 자산 관리")
    st.text_input(
        "비밀번호를 입력해주세요", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state and st.session_state["password_correct"] == False:
        st.error("비밀번호를 다시 확인해주세요!")

    st.markdown("---")
    st.markdown("### 💖 아껴쓰자! 예진이는 맘대로 써도 돼") 
    
    image_file = "main.jpg"
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists(image_file):
            st.image(image_file, caption="사랑하는 우리 가족", use_container_width=True)
        else:
            st.image("https://placekitten.com/400/300", caption="사진을 올려주세요!", use_container_width=True)

    return False

# --- 2. 메인 화면 ---
def main():
    st.set_page_config(page_title="우리집 가계부", layout="wide", page_icon="🏡")

    if not check_password():
        return

    today = datetime.now()

    if "home_year" not in st.session_state:
        st.session_state.home_year = today.year
    if "home_month" not in st.session_state:
        st.session_state.home_month = today.month

    with st.sidebar:
        st.title("🏡 우리집 가계부")
        menu = st.radio("메뉴 이동", ["📝 입력 및 홈", "🔄 고정 지출 관리", "📅 달력", "📊 분석"])
        st.markdown("---")
        target_budget = st.number_input("목표 생활비(원)", value=2000000, step=100000, format="%d")

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
        
        nav1, nav2, nav3 = st.columns([1, 2, 1])
        with nav1:
            if st.button("◀ 이전 달", use_container_width=True):
                st.session_state.home_month -= 1
                if st.session_state.home_month < 1:
                    st.session_state.home_month = 12
                    st.session_state.home_year -= 1
                st.rerun()
        with nav2:
            st.markdown(f"<h3 style='text-align: center;'>{st.session_state.home_year}년 {st.session_state.home_month}월 내역</h3>", unsafe_allow_html=True)
        with nav3:
            if st.button("다음 달 ▶", use_container_width=True):
                st.session_state.home_month += 1
                if st.session_state.home_month > 12:
                    st.session_state.home_month = 1
                    st.session_state.home_year += 1
                st.rerun()

        if not df.empty:
            this_month_df = df[(df['날짜'].dt.month == st.session_state.home_month) & (df['날짜'].dt.year == st.session_state.home_year)]
            total_expense = this_month_df[this_month_df['구분']=='지출']['금액'].sum()
        else:
            this_month_df = pd.DataFrame(columns=HEADERS)
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
            
            cat_options = INCOME_CATS if exp_type == "수입" else EXPENSE_CATS

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
            st.subheader(f"📋 {st.session_state.home_month}월 전체 내역 ({len(this_month_df)}건)")
            st.caption("표 왼쪽에 체크박스를 선택하고 휴지통을 누르거나 Delete키를 눌러 내역을 삭제할 수 있습니다.")
            button_placeholder = st.empty()
            
            if not this_month_df.empty:
                edit_df = this_month_df.sort_values(by='날짜', ascending=False).copy()
                edit_df['날짜'] = edit_df['날짜'].dt.strftime('%Y-%m-%d')
                edit_df = edit_df[['날짜', '구분', '금액', '카테고리', '내역', '사용자']]
                all_cats = list(set(INCOME_CATS + EXPENSE_CATS))

                dynamic_height = (len(edit_df) + 1) * 35 + 3

                # num_rows="dynamic" 옵션을 통해 삭제 기능 활성화
                edited_data = st.data_editor(
                    edit_df,
                    use_container_width=True,
                    height=dynamic_height,
                    num_rows="dynamic", # 추가 및 삭제 기능 켜기
                    hide_index=True,
                    column_config={
                        "금액": st.column_config.NumberColumn(format="%d원"),
                        "카테고리": st.column_config.SelectboxColumn(options=all_cats),
                        "사용자": st.column_config.SelectboxColumn(options=["해기", "에디", "같이"]),
                        "구분": st.column_config.SelectboxColumn(options=["지출", "수입"])
                    }
                )

                with button_placeholder:
                    if st.button("💾 저장 (수정/삭제 완료)", type="primary", use_container_width=True, key="save_home"):
                        with st.spinner("구글 시트 연동 중..."):
                            # 1. 삭제된 행 처리
                            # 원본에는 있는데 편집된 데이터에는 없는 인덱스를 찾음
                            deleted_indices = set(edit_df.index) - set(edited_data.index)
                            if deleted_indices:
                                delete_multiple_rows(list(deleted_indices))
                            
                            # 2. 수정된 데이터 처리
                            # 편집된 데이터가 원본과 다른 경우 업데이트 수행
                            for index, row in edited_data.iterrows():
                                if index in edit_df.index: # 기존에 있던 행이면 수정 여부 검사
                                    original_row = edit_df.loc[index]
                                    for col in HEADERS:
                                        if str(row[col]) != str(original_row[col]):
                                            update_cell(index, col, row[col])
                                else:
                                    # 새로 추가된 행(UI 상에서 직접 + 눌러 추가한 경우)
                                    # (권장하지는 않으나, 예외 처리)
                                    add_row(row['날짜'], row['구분'], row['사용자'], row['카테고리'], row['내역'], row['금액'])

                            st.success("반영되었습니다!")
                            time.sleep(1)
                            st.rerun()

            else:
                st.info("해당 월의 데이터가 없습니다.")

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
    # [탭 3] 달력 (버튼 클릭형 팝업 적용)
    # ==========================
    elif menu == "📅 달력":
        st.header("📅 월별 달력 (날짜를 클릭하세요!)")
        c1, c2 = st.columns(2)
        sel_year = c1.number_input("연도", value=today.year)
        sel_month = c2.number_input("월", value=today.month, min_value=1, max_value=12)
        
        calendar.setfirstweekday(calendar.SUNDAY)
        cal = calendar.monthcalendar(sel_year, sel_month)
        week_korean = ['일', '월', '화', '수', '목', '금', '토']
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        cols = st.columns(7)
        for i, w in enumerate(week_korean):
            color = "red" if i == 0 else "blue" if i == 6 else "black"
            cols[i].markdown(f"<div style='text-align:center; color:{color}; font-weight:bold;'>{w}</div>", unsafe_allow_html=True)

        if not df.empty:
            month_data = df[(df['날짜'].dt.year == sel_year) & (df['날짜'].dt.month == sel_month)]
        else:
            month_data = pd.DataFrame(columns=HEADERS)

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day != 0:
                        day_df = month_data[month_data['날짜'].dt.day == day] if not month_data.empty else pd.DataFrame(columns=HEADERS)
                        exp = day_df[day_df['구분']=='지출']['금액'].sum()
                        inc = day_df[day_df['구분']=='수입']['금액'].sum()
                        
                        btn_label = f"{day}일"
                        if exp > 0: btn_label += f"\n-{exp:,.0f}"
                        if inc > 0: btn_label += f"\n+{inc:,.0f}"
                        
                        if st.button(btn_label, key=f"cal_{sel_year}_{sel_month}_{day}", use_container_width=True):
                            popup_details(day_df, f"📅 {sel_year}년 {sel_month}월 {day}일 상세 내역")
                    else:
                        st.write("") 

        st.divider()
        st.info("💡 달력의 날짜 칸(버튼)을 직접 터치하시면 팝업으로 상세 내역을 확인할 수 있습니다.")

    # ==========================
    # [탭 4] 맞춤형 분석 (차트 팝업 적용)
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
                    m1.metric("선택 기간 수입 합계", f"{total_inc:,.0f}원")
                    m2.metric("선택 기간 지출 합계", f"{total_exp:,.0f}원")

                    st.divider()

                    st.subheader("📈 지출 분석 차트")
                    exp_df = filtered_df[filtered_df['구분'] == '지출']
                    
                    if not exp_df.empty:
                        chart_type = st.radio(
                            "보고 싶은 차트를 선택하세요", 
                            ["카테고리별 비중 (원형)", "일별 지출 흐름 (막대)"], 
                            horizontal=True
                        )
                        
                        if chart_type == "카테고리별 비중 (원형)":
                            cat_sum = exp_df.groupby('카테고리')['금액'].sum().reset_index()
                            fig = px.pie(cat_sum, values='금액', names='카테고리', hole=0.4)
                            fig.update_traces(
                                textposition='inside', 
                                textinfo='percent+label',
                                hovertemplate='%{label}<br>%{value:,.0f}원 (%{percent})'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                            st.markdown("#### 🔍 특정 카테고리 세부내역 보기")
                            p_col1, p_col2 = st.columns([3, 1])
                            with p_col1:
                                pop_cat = st.selectbox("항목을 선택하세요", exp_df['카테고리'].unique(), label_visibility="collapsed")
                            with p_col2:
                                if st.button("팝업 열기", type="primary", use_container_width=True):
                                    cat_df = exp_df[exp_df['카테고리'] == pop_cat]
                                    popup_details(cat_df, f"📊 [{pop_cat}] 상세 내역")
                            
                        elif chart_type == "일별 지출 흐름 (막대)":
                            daily_sum = exp_df.groupby('날짜')['금액'].sum().reset_index()
                            fig = px.bar(daily_sum, x='날짜', y='금액')
                            fig.update_traces(
                                texttemplate='%{y:,.0f}원', 
                                textposition='outside',
                                hovertemplate='%{x}<br>%{y:,.0f}원'
                            )
                            fig.update_yaxes(tickformat=",.0f", title="금액 (원)")
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("선택하신 기간에 지출 내역이 없어 그래프를 그릴 수 없습니다.")
                    
                    st.divider()

                    st.subheader("📝 상세 내역 수정")
                    anal_button_placeholder = st.empty()

                    display_filtered = filtered_df.sort_values(by='날짜', ascending=False).copy()
                    display_filtered['날짜'] = display_filtered['날짜'].dt.strftime('%Y-%m-%d')
                    display_filtered = display_filtered[['날짜', '구분', '금액', '카테고리', '내역', '사용자']]

                    anal_height = (len(display_filtered) + 1) * 35 + 3

                    # 분석 탭에서도 삭제 기능 활성화
                    edited_anal = st.data_editor(
                        display_filtered,
                        use_container_width=True,
                        height=anal_height,
                        num_rows="dynamic",
                        hide_index=True,
                        column_config={
                            "금액": st.column_config.NumberColumn(format="%d원"),
                            "카테고리": st.column_config.SelectboxColumn(options=all_cats),
                            "사용자": st.column_config.SelectboxColumn(options=["해기", "에디", "같이"]),
                            "구분": st.column_config.SelectboxColumn(options=["지출", "수입"])
                        }
                    )

                    with anal_button_placeholder:
                        if st.button("💾 저장 (수정/삭제 완료)", type="primary", use_container_width=True, key="save_anal"):
                            with st.spinner("구글 시트 연동 중..."):
                                deleted_indices = set(display_filtered.index) - set(edited_anal.index)
                                if deleted_indices:
                                    delete_multiple_rows(list(deleted_indices))
                                
                                for index, row in edited_anal.iterrows():
                                    if index in display_filtered.index:
                                        original_row = display_filtered.loc[index]
                                        for col in HEADERS:
                                            if str(row[col]) != str(original_row[col]):
                                                update_cell(index, col, row[col])
                                    else:
                                        add_row(row['날짜'], row['구분'], row['사용자'], row['카테고리'], row['내역'], row['금액'])
                                
                                st.success("반영되었습니다!")
                                time.sleep(1)
                                st.rerun()

                else:
                    st.info("내역이 없습니다.")
            else:
                st.info("기간을 선택해주세요.")
                
if __name__ == '__main__':
    main()
