import streamlit as st
from datetime import datetime, date, time, timedelta
import uuid
from typing import List, Dict, Any
import json

st.set_page_config(page_title="ContentForge v9.0", layout="wide")


# ---------- helpers de estado ----------
def sget(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def reset_daily_counters(user: Dict[str, Any]):
    today_str = date.today().isoformat()
    if user.get("last_day") != today_str:
        user["last_day"] = today_str
        user["gen_today"] = 0
        user["planner_today"] = 0


# ---------- planos ----------
PLANS = {
    "Starter": {
        "gen_per_day": 5,
        "planner_per_day": 5,
        "has_analysis": False,
        "has_perf_tab": False,
        "has_pro_export": False,
    },
    "Pro": {
        "gen_per_day": 100,
        "planner_per_day": 999,
        "has_analysis": True,
        "has_perf_tab": True,
        "has_pro_export": True,
    },
}

# ---------- estado base ----------
user = sget(
    "user",
    {
        "brand": "Minha Marca",
        "niche": "Negócio local",
        "tone": "profissional",
        "voice": "Venda",
        "plan": "Starter",
        "last_day": date.today().isoformat(),
        "gen_today": 0,
        "planner_today": 0,
    },
)
reset_daily_counters(user)

generated_posts: List[Dict[str, Any]] = sget("generated_posts", [])
planner: List[Dict[str, Any]] = sget("planner", [])
done: List[Dict[str, Any]] = sget("done", [])
week_offset: int = sget("week_offset", 0)
selected_ev = sget("selected_ev", None)


# ---------- funções utilitárias ----------
def new_id() -> str:
    return uuid.uuid4().hex[:12]


def week_dates(offset_weeks: int = 0):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    monday = monday + timedelta(days=7 * offset_weeks)
    return [monday + timedelta(days=i) for i in range(7)]


# ---------- motor de geração (sem API externa) ----------
def build_caption(
    brand: str, niche: str, tone: str, objective: str, extra: str, mode: str
) -> str:
    if mode == "Venda":
        base_intro = f"{brand} traz-te hoje uma oportunidade séria no mundo de {niche}."
    elif mode == "Storytelling":
        base_intro = f"Tudo começou com uma ideia simples na {brand}: tornar {niche} mais especial."
    else:  # Educacional
        base_intro = f"Se queres levar {niche} a outro nível, começa por entender o essencial."

    if tone == "premium":
        tone_snip = "Detalhes, qualidade e consistência acima de tudo."
    elif tone == "casual":
        tone_snip = "Nada de complicar, só aquilo que realmente funciona."
    elif tone == "emocional":
        tone_snip = "Porque por trás de cada escolha existe uma história."
    else:  # profissional
        tone_snip = "Foco em resultados, sem ruído."

    objective_snip = objective.strip() if objective else ""
    extra_snip = extra.strip() if extra else ""

    parts = [base_intro]
    if objective_snip:
        parts.append(objective_snip)
    if extra_snip:
        parts.append(extra_snip)
    parts.append(tone_snip)

    caption = " ".join(p for p in parts if p)
    return caption


def basic_hashtags(niche: str):
    base = ["#marketing", "#negocios", "#conteudo", "#portugal", "#empreender"]
    niche_tag = "#" + niche.lower().replace(" ", "")
    if niche_tag not in base:
        base.insert(0, niche_tag)
    return base[:10]


def score_post(caption: str, objective: str, mode: str) -> Dict[str, float]:
    length = len(caption)
    has_offer = any(x in caption.lower() for x in ["desconto", "%", "hoje", "agora"])
    has_cta = any(
        x in caption.lower()
        for x in ["clica", "link", "comenta", "guarda", "envia", "partilha"]
    )
    has_emotion = any(
        x in caption.lower()
        for x in [
            "história",
            "historia",
            "sonho",
            "confiança",
            "seguro",
            "especial",
            "histórias",
        ]
    )

    clarity = 7.5
    if 80 <= length <= 260:
        clarity += 1.5
    elif length < 60:
        clarity -= 0.5
    elif length > 400:
        clarity -= 1.0

    conversion = 6.0 + (1.5 if has_offer else 0) + (1.0 if has_cta else 0)
    engagement = 6.5 + (0.8 if has_emotion else 0)
    emotion = 6.0 + (1.5 if has_emotion else 0)

    if mode == "Storytelling":
        engagement += 0.5
        emotion += 0.5
    elif mode == "Venda":
        conversion += 0.5

    platform_fit = 7.5  # simplificado
    cred = 7.0

    metrics = {
        "clarity": round(max(0, min(10, clarity)), 1),
        "conversion": round(max(0, min(10, conversion)), 1),
        "engagement": round(max(0, min(10, engagement)), 1),
        "emotion": round(max(0, min(10, emotion)), 1),
        "credibility": round(max(0, min(10, cred)), 1),
        "platform_fit": round(max(0, min(10, platform_fit)), 1),
    }
    final_score = (
        metrics["conversion"] * 0.25
        + metrics["engagement"] * 0.2
        + metrics["clarity"] * 0.2
        + metrics["platform_fit"] * 0.15
        + metrics["emotion"] * 0.1
        + metrics["credibility"] * 0.1
    )
    metrics["final"] = round(final_score, 1)
    return metrics


def generate_posts(
    brand: str,
    niche: str,
    tone: str,
    objective: str,
    extra: str,
    mode: str,
    plan: str,
) -> List[Dict[str, Any]]:
    posts = []
    variants = ["A", "B", "C"]
    for label in variants:
        caption = build_caption(brand, niche, tone, objective, extra, mode)
        full_caption = caption
        if label == "B":
            full_caption = (
                caption
                + " E se começasses hoje, sem esperar pelo momento perfeito?"
            )
        elif label == "C":
            full_caption = (
                caption
                + " O próximo passo está literalmente a um clique de distância."
            )

        # CTA
        if mode == "Venda":
            cta = "Clica no link da bio e dá o próximo passo."
        elif mode == "Storytelling":
            cta = "Se te identificas, guarda este post e partilha com alguém."
        else:
            cta = "Comenta 'QUERO' se queres mais conteúdos como este."

        body = full_caption + " " + cta
        tags = basic_hashtags(niche)
        metrics = score_post(body, objective, mode) if PLANS[plan]["has_analysis"] else {}

        posts.append(
            {
                "id": new_id(),
                "variant": label,
                "mode": mode,
                "caption": body,
                "hashtags": tags,
                "metrics": metrics,
            }
        )

    # escolher recomendação se houver análise
    if PLANS[plan]["has_analysis"]:
        best = max(posts, key=lambda p: p["metrics"].get("final", 0))
        best["recommended"] = True

    return posts


# ---------- UI base ----------
st.title("ContentForge v9.0")
st.caption(
    "Gera conteúdo inteligente, organiza num planner semanal e, no plano Pro, analisa a força de cada publicação."
)

# Sidebar
st.sidebar.header("Plano e perfil")
plan_names = list(PLANS.keys())
user["plan"] = st.sidebar.selectbox(
    "Plano", plan_names, index=plan_names.index(user["plan"])
)
reset_daily_counters(user)
plan_cfg = PLANS[user["plan"]]

st.sidebar.markdown(
    f"**Gerações hoje:** {user['gen_today']}/{plan_cfg['gen_per_day']}"
)
st.sidebar.markdown(
    f"**Tarefas no planner hoje:** {user['planner_today']}/{plan_cfg['planner_per_day']}"
)

user["brand"] = st.sidebar.text_input("Marca", user["brand"])
user["niche"] = st.sidebar.text_input("Nicho/tema", user["niche"])
user["tone"] = st.sidebar.selectbox(
    "Tom de voz",
    ["profissional", "premium", "casual", "emocional"],
    index=["profissional", "premium", "casual", "emocional"].index(user["tone"]),
)
user["voice"] = st.sidebar.selectbox(
    "Modo de copy",
    ["Venda", "Storytelling", "Educacional"],
    index=["Venda", "Storytelling", "Educacional"].index(user["voice"]),
)

tab_gen, tab_plan, tab_perf, tab_exp = st.tabs(
    ["✨ Gerar", "📅 Planner", "📈 Performance", "📤 Export"]
)


# ---------- Tab Gerar ----------
with tab_gen:
    st.subheader("✨ Geração de conteúdo")
    col1, col2 = st.columns([2, 1])
    with col1:
        objective = st.text_input("O que queres comunicar hoje?", "")
        extra = st.text_area("Informação extra (opcional)", "")
    with col2:
        st.write("")
        st.write("")
        can_gen = user["gen_today"] < plan_cfg["gen_per_day"]
        gen_btn = st.button("⚡ Gerar agora", disabled=not can_gen)
        if not can_gen:
            st.info("Limite diário de gerações atingido para o plano atual.")

    if gen_btn and can_gen:
        posts = generate_posts(
            user["brand"],
            user["niche"],
            user["tone"],
            objective,
            extra,
            user["voice"],
            user["plan"],
        )
        st.session_state["generated_posts"] = posts
        user["gen_today"] += 1

    generated_posts = sget("generated_posts", [])
    if generated_posts:
        st.markdown("#### Resultados")
        cols = st.columns(3)
        for i, post in enumerate(generated_posts):
            with cols[i % 3]:
                st.markdown("---")
                badge = ""
                if post.get("recommended"):
                    badge = " 🌟 **Nossa recomendação**"
                st.markdown(f"**Variação {post['variant']}**{badge}")
                st.write(post["caption"])
                st.caption("Hashtags: " + " ".join(post["hashtags"]))

                # campos para planner
                d = st.date_input(
                    "Dia", value=date.today(), key=f"date_{post['id']}"
                )
                t = st.time_input(
                    "Hora", value=time(18, 0), key=f"time_{post['id']}"
                )
                can_add = user["planner_today"] < plan_cfg["planner_per_day"]
                if st.button(
                    "➕ Adicionar ao planner",
                    key=f"add_{post['id']}",
                    disabled=not can_add,
                ):
                    planner.append(
                        {
                            "id": post["id"],
                            "title": f"Post {post['variant']}",
                            "caption": post["caption"],
                            "hashtags": post["hashtags"],
                            "day": d.isoformat(),
                            "time": t.strftime("%H:%M"),
                        }
                    )
                    user["planner_today"] += 1
                    st.success("Adicionado ao planner.")

        # análise automática (só Pro)
        if plan_cfg["has_analysis"]:
            st.markdown("#### 📊 Análise automática")
            import pandas as pd

            rows = []
            for post in generated_posts:
                m = post.get("metrics") or {}
                rows.append(
                    {
                        "Variação": post["variant"],
                        "Clareza": m.get("clarity", 0),
                        "Conversão": m.get("conversion", 0),
                        "Engajamento": m.get("engagement", 0),
                        "Emoção": m.get("emotion", 0),
                        "Credibilidade": m.get("credibility", 0),
                        "Plataforma": m.get("platform_fit", 0),
                        "Score final": m.get("final", 0),
                        "Recomendado": "Sim"
                        if post.get("recommended")
                        else "—",
                    }
                )
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            best = max(
                generated_posts,
                key=lambda p: p.get("metrics", {}).get("final", 0),
            )
            best_m = best.get("metrics", {})
            st.markdown(
                f"**Sugestão:** publica a variação {best['variant']} "
                f"(score {best_m.get('final', 0)}/10, conversão {best_m.get('conversion', 0)}/10)."
            )
        else:
            st.info("Análise automática disponível no plano Pro.")


# ---------- Tab Planner ----------
with tab_plan:
    st.subheader("📅 Planner semanal")

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("« Semana anterior"):
            st.session_state["week_offset"] = week_offset - 1
            st.experimental_rerun()
    with c2:
        if st.button("Próxima semana »"):
            st.session_state["week_offset"] = week_offset + 1
            st.experimental_rerun()

    days = week_dates(week_offset)
    start, end = days[0], days[-1]
    st.caption(f"Semana de {start.strftime('%d/%m')} a {end.strftime('%d/%m')}")

    cols = st.columns(7)
    for idx, day in enumerate(days):
        with cols[idx]:
            st.markdown(f"**{day.strftime('%a %d/%m')}**")
            day_str = day.isoformat()
            todays = [ev for ev in planner if ev["day"] == day_str]
            if not todays:
                st.caption("— sem posts —")
            for ev in todays:
                if st.button(
                    f"🕒 {ev['time']} · {ev['title']}",
                    key=f"open_{ev['id']}",
                ):
                    st.session_state["selected_ev"] = ev

    selected_ev = sget("selected_ev", None)
    if selected_ev:
        st.markdown("---")
        st.markdown("### Detalhes da tarefa")
        st.write(f"**Título:** {selected_ev['title']}")
        st.write(f"**Dia:** {selected_ev['day']} às {selected_ev['time']}")
        st.write("**Legenda:**")
        st.write(selected_ev["caption"])
        st.write("**Hashtags:**")
        st.code(" ".join(selected_ev["hashtags"]))

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if not plan_cfg["has_perf_tab"]:
                st.button("✅ Concluído (Pro)", disabled=True)
                st.caption("Disponível no plano Pro.")
            else:
                if st.button("✅ Concluído"):
                    done.append(
                        {**selected_ev, "completed_at": datetime.utcnow().isoformat()}
                    )
                    planner[:] = [
                        e for e in planner if e["id"] != selected_ev["id"]
                    ]
                    st.session_state["selected_ev"] = None
                    st.success("Tarefa marcada como concluída.")
        with col_b:
            if st.button("🗑️ Remover do planner"):
                planner[:] = [e for e in planner if e["id"] != selected_ev["id"]]
                st.session_state["selected_ev"] = None
                st.warning("Tarefa removida.")
        with col_c:
            if st.button("Fechar detalhes"):
                st.session_state["selected_ev"] = None


# ---------- Tab Performance ----------
with tab_perf:
    st.subheader("📈 Performance")
    if not plan_cfg["has_perf_tab"]:
        st.info("Funcionalidades de performance disponíveis no plano Pro.")
    else:
        if not done:
            st.info("Ainda não existem tarefas concluídas.")
        else:
            import pandas as pd

            rows = []
            for ev in done:
                rows.append(
                    {
                        "Dia": ev["day"],
                        "Hora": ev["time"],
                        "Título": ev["title"],
                    }
                )
            df = pd.DataFrame(rows).sort_values(["Dia", "Hora"])
            st.markdown("#### Histórico de publicações concluídas")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown(
                "_Nesta versão, as métricas são ilustrativas; na futura versão Pro+ "
                "serão ligadas à conta real._"
            )


# ---------- Tab Export ----------
with tab_exp:
    st.subheader("📤 Export")

    data = {
        "user": user,
        "planner": planner,
        "done": done,
    }

    # export básico .txt (Starter + Pro)
    txt_lines = []
    for ev in planner:
        txt_lines.append(f"{ev['day']} {ev['time']} - {ev['title']}")
        txt_lines.append(ev["caption"])
        txt_lines.append(" ".join(ev["hashtags"]))
        txt_lines.append("")
    txt_content = "\n".join(txt_lines)

    st.download_button(
        "Descarregar plano em .txt",
        data=txt_content.encode("utf-8"),
        file_name="planner.txt",
        mime="text/plain",
    )

    # export Pro .csv
    if plan_cfg["has_pro_export"]:
        csv_lines = ["day,time,title,caption,hashtags"]
        for ev in planner:
            row = [
                ev["day"],
                ev["time"],
                ev["title"].replace(",", " "),
                ev["caption"].replace(",", " "),
                " ".join(ev["hashtags"]).replace(",", " "),
            ]
            csv_lines.append(",".join(row))
        csv_content = "\n".join(csv_lines)
        st.download_button(
            "Descarregar plano em .csv (Pro)",
            data=csv_content.encode("utf-8"),
            file_name="planner.csv",
            mime="text/csv",
        )
    else:
        st.info("Export .csv disponível no plano Pro.")
