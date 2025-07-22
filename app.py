import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import plotly.express as px

# --- ページ設定 ---
st.set_page_config(
    page_title="AIレシピ＆栄養管理",
    page_icon="🍲",
    layout="wide"
)

# --- ユーティリティ関数 ---
def extract_nutrition_info(text):
    """
    AIが生成したテキストから栄養情報を抽出する関数。
    正規表現を使って「カロリー: XXXkcal」「タンパク質: YYYg」などの形式を検出。
    """
    nutrition = {
        "カロリー(kcal)": 0.0, # float型で初期化
        "タンパク質(g)": 0.0,
        "脂質(g)": 0.0,
        "炭水化物(g)": 0.0
    }

    # 各栄養素に対応する正規表現パターン
    # AIの出力が「カロリー：350kcal」のように全角コロンで出力される可能性も考慮し、
    # コロンの前後に\s*（空白文字0回以上）を追加し、コロン自体も全角半角両方に対応
    patterns = {
        "カロリー(kcal)": r"カロリー\s*[：:]\s*(\d+(\.\d+)?)\s*kcal",
        "タンパク質(g)": r"タンパク質\s*[：:]\s*(\d+(\.\d+)?)\s*g",
        "脂質(g)": r"脂質\s*[：:]\s*(\d+(\.\d+)?)\s*g",
        "炭水化物(g)": r"炭水化物\s*[：:]\s*(\d+(\.\d+)?)\s*g"
    }

    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            try:
                value = float(match.group(1))
                nutrition[key] = value
                st.sidebar.write(f"✅ {key}: {value} (抽出成功)")
            except ValueError:
                st.sidebar.write(f"❌ {key}: 値の変換失敗 (マッチ: {match.group(1)})")
        else:
            st.sidebar.write(f"❌ {key}: パターン不一致")


    return nutrition

# --- セッションステートの初期化 ---
if "generated_recipes" not in st.session_state:
    st.session_state.generated_recipes = []

if "nutrition_data" not in st.session_state:
    st.session_state.nutrition_data = pd.DataFrame(
        columns=["日付", "レシピ名", "カロリー(kcal)", "タンパク質(g)", "脂質(g)", "炭水化物(g)"]
    )

# --- サイドバー (APIキー入力とアプリ情報) ---
st.sidebar.header("アプリ設定")

try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    gemini_api_key = st.sidebar.text_input(
        "Gemini APIキーを入力してください:",
        type="password",
        help="Google AI Studio (https://aistudio.google.com/) でAPIキーを取得し、ここにペーストしてください。"
    )

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    st.sidebar.success("Gemini APIキーが設定されました。")
    if "gemini_model" not in st.session_state:
        st.session_state.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.sidebar.warning("Gemini APIキーを設定してください。AI機能は利用できません。")

st.sidebar.markdown("---")
st.sidebar.info("このアプリは、AIがあなたにぴったりのレシピを提案し、日々の栄養管理をサポートします。")

# --- メインコンテンツ ---
st.title("🍲 AIレシピジェネレーター＆栄養管理アプリ")
st.markdown("あなたの冷蔵庫にある食材や好みに合わせて、AIが最適なレシピを提案します。")

# --- タブの作成 ---
tab1, tab2, tab3 = st.tabs(["✨ レシピ生成", "📊 栄養管理", "📚 レシピ履歴"])

with tab1:
    st.header("レシピ生成")
    if gemini_api_key:
        st.write("使いたい食材や好みを入力して、AIにレシピを提案してもらいましょう！")

        with st.form("recipe_form"):
            st.subheader("レシピの要望を入力してください")

            ingredients_input = st.text_area(
                "使いたい食材（複数ある場合は改行またはカンマで区切ってください）例: 鶏むね肉、玉ねぎ、トマト、きのこ",
                height=100
            )

            genre = st.selectbox(
                "料理のジャンル（任意）",
                ["指定なし", "和食", "洋食", "中華", "イタリアン", "フレンチ", "エスニック", "その他"]
            )

            purpose = st.selectbox(
                "食事の目的（任意）",
                ["指定なし", "健康的", "ダイエット", "筋肉増強", "節約", "時短", "パーティー"]
            )

            cooking_time = st.slider(
                "調理時間の目安（分）",
                min_value=10, max_value=120, value=30, step=5
            )

            allergies = st.text_input(
                "アレルギー情報（例: 卵、乳製品）",
                placeholder="例: 小麦、そば"
            )

            submitted = st.form_submit_button("レシピを生成する")

        if submitted:
            if not ingredients_input:
                st.warning("使いたい食材を少なくとも1つ入力してください。")
            else:
                with st.spinner("AIが最高のレシピを考案中です..."):
                    try:
                        formatted_ingredients = ", ".join([ing.strip() for ing in ingredients_input.split(',') if ing.strip()])

                        prompt = f"""あなたは優秀な料理研究家であり、栄養士でもあります。
                        以下の情報を元に、健康的で美味しいレシピを考案してください。
                        制約事項：
                        - レシピは具体的な材料と詳細な手順で構成してください。
                        - 栄養情報（推定カロリー(kcal)、タンパク質(g)、脂質(g)、炭水化物(g)）を必ず含めてください。
                          栄養情報は箇条書きで分かりやすく記述し、それぞれ具体的な数値（例: カロリー: 350kcal, タンパク質: 20g）を記載してください。
                        - 調理時間は{cooking_time}分以内を目安としてください。
                        - アレルギー情報がある場合は、それに配慮してください。

                        ユーザーの要望：
                        - 使いたい食材：{formatted_ingredients}
                        - 料理のジャンル：{genre if genre != "指定なし" else "特に指定なし"}
                        - 食事の目的：{purpose if purpose != "指定なし" else "特に指定なし"}
                        - アレルギー：{allergies if allergies else "なし"}

                        レシピ名：
                        材料：
                        作り方：
                        栄養情報：
                        """

                        response = st.session_state.gemini_model.generate_content(prompt)
                        recipe_text = response.text

                        st.subheader("🎉 AIが提案するレシピです！")
                        st.markdown(recipe_text)

                
                        nutrition_values = extract_nutrition_info(recipe_text) # 抽出関数を呼び出し
                    
                        new_nutrition_row = {
                            "日付": pd.Timestamp.now().strftime("%Y-%m-%d"),
                            "レシピ名": recipe_text.splitlines()[0].replace("レシピ名：", "").strip() if "レシピ名：" in recipe_text else "不明なレシピ",
                            "カロリー(kcal)": nutrition_values["カロリー(kcal)"],
                            "タンパク質(g)": nutrition_values["タンパク質(g)"],
                            "脂質(g)": nutrition_values["脂質(g)"],
                            "炭水化物(g)": nutrition_values["炭水化物(g)"]
                        }
                        
                        st.session_state.nutrition_data = pd.concat([
                            st.session_state.nutrition_data,
                            pd.DataFrame([new_nutrition_row])
                        ], ignore_index=True)

                        st.session_state.generated_recipes.append({
                            "inputs": {
                                "食材": ingredients_input,
                                "ジャンル": genre,
                                "目的": purpose,
                                "時間": cooking_time,
                                "アレルギー": allergies
                            },
                            "recipe_text": recipe_text,
                            "nutrition_info": nutrition_values,
                            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.success("レシピが生成され、履歴と栄養データに保存されました！")

                    except Exception as e:
                        st.error(f"レシピ生成中にエラーが発生しました: {e}")
                        st.info("APIキーが有効か、または入力内容が適切かご確認ください。")
    else:
        st.info("AIレシピ生成機能を利用するには、サイドバーでGemini APIキーを設定してください。")

with tab2:
    st.header("📊 栄養管理")
    st.write("記録された食事の栄養データを閲覧・分析できます。")


    if not st.session_state.nutrition_data.empty:
        display_option = st.radio(
            "データの表示形式を選択してください:",
            ("詳細データ", "日ごとのサマリー"),
            horizontal=True,
            key="display_option_radio"
        )

        if display_option == "詳細データ":
            st.subheader("記録されたすべての栄養データ")
            st.dataframe(st.session_state.nutrition_data, use_container_width=True)
            
            @st.cache_data
            def convert_df_to_csv(df):
                return df.to_csv(index=False).encode('utf-8')

            csv = convert_df_to_csv(st.session_state.nutrition_data)
            st.download_button(
                label="栄養データをCSVでダウンロード",
                data=csv,
                file_name="nutrition_data.csv",
                mime="text/csv",
            )

        elif display_option == "日ごとのサマリー":
            st.subheader("日ごとの栄養サマリー")
            daily_summary = st.session_state.nutrition_data.groupby("日付").sum(numeric_only=True)
            st.dataframe(daily_summary, use_container_width=True)

            st.subheader("栄養摂取量のトレンドと内訳")
            
            st.markdown("##### 日ごとの栄養摂取量のトレンド")
            nutrient_to_plot_line = st.selectbox(
                "トレンド表示する栄養素を選択してください:",
                ["カロリー(kcal)", "タンパク質(g)", "脂質(g)", "炭水化物(g)"],
                key="nutrient_line_selector"
            )
            if not daily_summary.empty:
                plot_data_line = daily_summary.reset_index()
                fig_line = px.line(
                    plot_data_line,
                    x="日付",
                    y=nutrient_to_plot_line,
                    title=f"日ごとの{nutrient_to_plot_line}摂取量",
                    labels={"日付": "日付", nutrient_to_plot_line: f"{nutrient_to_plot_line} (合計)"}
                )
                fig_line.update_xaxes(dtick="D1", tickformat="%m/%d")
                st.plotly_chart(fig_line, use_container_width=True)
            
            st.markdown("---")
            
            st.markdown("##### 主要栄養素の合計内訳（全期間）")
            total_nutrition = st.session_state.nutrition_data[["タンパク質(g)", "脂質(g)", "炭水化物(g)"]].sum().reset_index()
            total_nutrition.columns = ["栄養素", "合計量(g)"]

            if not total_nutrition.empty:
                fig_bar = px.bar(
                    total_nutrition,
                    x="栄養素",
                    y="合計量(g)",
                    title="主要栄養素の合計量",
                    labels={"栄養素": "栄養素", "合計量(g)": "合計摂取量 (g)"}
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                st.markdown("##### 三大栄養素の割合")
                fig_pie = px.pie(
                    total_nutrition,
                    values="合計量(g)",
                    names="栄養素",
                    title="三大栄養素の割合",
                    hole=0.3
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                
            else:
                st.info("まだ栄養データがありません。レシピを生成して記録しましょう！")

    else:
        st.info("まだ栄養データがありません。レシピを生成して記録しましょう！")

with tab3:
    st.header("📚 レシピ履歴")
    st.write("これまでに生成・保存したレシピを閲覧できます。")

    if st.session_state.generated_recipes:
        for i, recipe_entry in enumerate(reversed(st.session_state.generated_recipes)):
            recipe_key = f"recipe_{i}_{recipe_entry['timestamp']}"
            
            with st.expander(f"**{recipe_entry['timestamp']}** - {recipe_entry['recipe_text'].splitlines()[0].replace('レシピ名：', '').strip()}"):
                st.markdown(recipe_entry["recipe_text"])
                
                if "nutrition_info" in recipe_entry and isinstance(recipe_entry["nutrition_info"], dict):
                    st.markdown("---")
                    st.subheader("💡 栄養情報")
                    nut_info = recipe_entry["nutrition_info"]
                    
                    # 各栄養素が存在するかチェックし、表示
                    # .get() を使うとキーが存在しない場合にエラーにならない
                    st.write(f"**カロリー:** {nut_info.get('カロリー(kcal)', 0.0):.1f}kcal")
                    st.write(f"**タンパク質:** {nut_info.get('タンパク質(g)', 0.0):.1f}g")
                    st.write(f"**脂質:** {nut_info.get('脂質(g)', 0.0):.1f}g")
                    st.write(f"**炭水化物:** {nut_info.get('炭水化物(g)', 0.0):.1f}g")
                
                st.markdown("---")
                st.subheader("入力情報")
                st.json(recipe_entry["inputs"])
    else:
        st.info("まだレシピが生成されていません。レシピ生成タブで新しいレシピを作成しましょう！")