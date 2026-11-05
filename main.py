import re
from itertools import combinations

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍱",
    layout="wide",
)

st.title("🍱 급식 규칙 찾기")
st.write(
    "184일의 송탄고 중식에서 함께 나온 메뉴와 메뉴 사이의 규칙을 찾아봅니다."
)

CSV_URL = (
    "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/"
    "songtan_meals_184.csv"
)


# --------------------------------------------------
# 데이터 불러오기 및 전처리
# --------------------------------------------------

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL, encoding="utf-8")

    required_columns = ["날짜", "식사", "메뉴"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"CSV에 필요한 열이 없습니다: {missing}")

    def clean_menu(menu):
        menu = str(menu)

        # 괄호와 괄호 안의 내용 제거
        menu = re.sub(r"\([^)]*\)", "", menu)

        return menu.strip()

    baskets = []

    for menu_text in df["메뉴"].fillna(""):
        menus = [
            clean_menu(menu)
            for menu in str(menu_text).split("|")
        ]

        # 빈 메뉴 제거 및 하루 안의 중복 제거
        menus = sorted(set(menu for menu in menus if menu))

        baskets.append(menus)

    return df, baskets


try:
    df, baskets = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()


# --------------------------------------------------
# 메뉴별 등장 일수와 메뉴 쌍 계산
# --------------------------------------------------

total_days = len(baskets)

menu_counts = {}
pair_counts = {}

for basket in baskets:

    for menu in basket:
        menu_counts[menu] = menu_counts.get(menu, 0) + 1

    for menu_a, menu_b in combinations(basket, 2):
        pair = (menu_a, menu_b)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1


# --------------------------------------------------
# 연관 규칙 계산
# --------------------------------------------------

rules = []

for (menu_a, menu_b), count in pair_counts.items():

    support = count / total_days

    # A → B
    confidence_ab = count / menu_counts[menu_a]
    lift_ab = confidence_ab / (menu_counts[menu_b] / total_days)

    rules.append({
        "조건": menu_a,
        "결과": menu_b,
        "동시": count,
        "지지도": support,
        "신뢰도": confidence_ab,
        "향상도": lift_ab,
    })

    # B → A
    confidence_ba = count / menu_counts[menu_b]
    lift_ba = confidence_ba / (menu_counts[menu_a] / total_days)

    rules.append({
        "조건": menu_b,
        "결과": menu_a,
        "동시": count,
        "지지도": support,
        "신뢰도": confidence_ba,
        "향상도": lift_ba,
    })


rules_df = pd.DataFrame(rules)

if rules_df.empty:
    st.warning("함께 나온 메뉴 쌍이 없습니다.")
    st.stop()


# --------------------------------------------------
# 상단 요약
# --------------------------------------------------

menu_count = len(menu_counts)
pair_count = len(pair_counts)

st.markdown(
    f"**급식 일수:** {total_days}일　|　"
    f"**메뉴 종류 수:** {menu_count}개　|　"
    f"**함께 나온 메뉴 쌍 수:** {pair_count}개"
)

st.divider()


# --------------------------------------------------
# 메뉴 좁혀 보기 및 정렬
# --------------------------------------------------

left, right = st.columns([2, 1])

with left:
    selected_menu = st.selectbox(
        "규칙 좁혀 보기",
        options=["전체 메뉴"] + sorted(menu_counts.keys()),
        key="rule_menu_select",
    )

with right:
    sort_option = st.selectbox(
        "정렬 기준",
        options=["향상도 순", "신뢰도 순", "동시 순"],
    )


# --------------------------------------------------
# 최소 동시 일수 슬라이더
# --------------------------------------------------

min_count = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
)

# 선택한 메뉴에 해당하는 규칙만 남기기
filtered_df = rules_df.copy()

if selected_menu != "전체 메뉴":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ]

# 최소 동시 일수 적용
filtered_df = filtered_df[
    filtered_df["동시"] >= min_count
]

# 정렬
sort_columns = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}

sort_column = sort_columns[sort_option]

filtered_df = filtered_df.sort_values(
    by=[sort_column, "동시", "신뢰도"],
    ascending=[False, False, False],
).reset_index(drop=True)


# --------------------------------------------------
# 연관 규칙 표
# --------------------------------------------------

st.subheader("메뉴 연관 규칙")

st.write(f"현재 조건에 맞는 규칙: **{len(filtered_df)}개**")

if filtered_df.empty:
    st.info("조건에 맞는 규칙이 없습니다.")
else:
    display_df = filtered_df.copy()

    display_df["지지도"] = (
        (display_df["지지도"] * 100).round(2).astype(str) + "%"
    )

    display_df["신뢰도"] = (
        (display_df["신뢰도"] * 100).round(2).astype(str) + "%"
    )

    display_df["향상도"] = display_df["향상도"].round(3)

    st.dataframe(
        display_df[
            ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
        ],
        hide_index=True,
        width="stretch",
    )

    st.caption(
        "지지도는 전체 급식 중 두 메뉴가 함께 나온 비율, "
        "신뢰도는 조건 메뉴가 나온 날 중 결과 메뉴도 나온 비율입니다. "
        "향상도는 결과 메뉴가 평소보다 얼마나 자주 함께 나오는지를 나타냅니다."
    )


# --------------------------------------------------
# 향상도 상위 10개 가로 막대그래프
# --------------------------------------------------

st.divider()
st.subheader("향상도 상위 10개 규칙")

if filtered_df.empty:
    st.info("그래프로 표시할 규칙이 없습니다.")
else:
    top10 = filtered_df.sort_values(
        "향상도",
        ascending=False,
    ).head(10).copy()

    top10["규칙"] = top10["조건"] + " → " + top10["결과"]

    # 가장 큰 값이 위에 오도록 역순 정렬
    top10 = top10.sort_values("향상도", ascending=True)

    fig = px.bar(
        top10,
        x="향상도",
        y="규칙",
        orientation="h",
        text=top10["향상도"].round(3),
        hover_data={
            "조건": True,
            "결과": True,
            "동시": True,
            "지지도": ":.2%",
            "신뢰도": ":.2%",
            "향상도": ":.3f",
            "규칙": False,
        },
        labels={
            "향상도": "향상도",
            "규칙": "연관 규칙",
        },
        title="향상도가 높은 메뉴 연관 규칙 TOP 10",
    )

    fig.update_layout(
        yaxis_title="",
        xaxis_title="향상도",
        showlegend=False,
        height=max(400, len(top10) * 45),
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
    )

    st.plotly_chart(fig, width="stretch")


# --------------------------------------------------
# 함께 나온 적 없는 짝
# --------------------------------------------------

st.divider()
st.subheader("함께 나온 적 없는 짝")

st.write(
    "선택한 메뉴와 같은 날 한 번도 함께 나오지 않았지만, "
    "각각 10일 이상 나온 메뉴를 찾아봅니다."
)

selected_menu_for_absence = st.selectbox(
    "함께 나온 적 없는 짝을 찾을 메뉴",
    options=sorted(menu_counts.keys()),
    key="absence_menu_select",
)

# 선택한 메뉴와 함께 나온 적이 있는 메뉴
appeared_with = set()

for (menu_a, menu_b), count in pair_counts.items():
    if menu_a == selected_menu_for_absence:
        appeared_with.add(menu_b)

    elif menu_b == selected_menu_for_absence:
        appeared_with.add(menu_a)


# 함께 나온 적이 없고, 혼자서는 10일 이상 나온 메뉴
never_together = []

for menu, days in menu_counts.items():

    if menu == selected_menu_for_absence:
        continue

    if menu in appeared_with:
        continue

    if days < 10:
        continue

    never_together.append({
        "메뉴": menu,
        "나온 날": days,
    })


never_together_df = pd.DataFrame(never_together)

# 나온 날이 많은 순으로 정렬
if not never_together_df.empty:
    never_together_df = never_together_df.sort_values(
        by="나온 날",
        ascending=False,
    ).reset_index(drop=True)

selected_menu_days = menu_counts[selected_menu_for_absence]

st.write(
    f"**{selected_menu_for_absence}**: "
    f"{selected_menu_days}일 출현"
)

if never_together_df.empty:
    st.info(
        "선택한 메뉴와 함께 나온 적이 없고, "
        "10일 이상 나온 메뉴가 없습니다."
    )
else:
    st.write(
        f"함께 나온 적 없는 메뉴: **{len(never_together_df)}개**"
    )

    st.dataframe(
        never_together_df,
        hide_index=True,
        width="stretch",
    )
