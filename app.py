import json
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st
from openai import OpenAI

# =========================
# CONFIGURAÇÃO BÁSICA
# =========================

st.set_page_config(
    page_title="ContentForge v9.0",
    page_icon="🍏",
    layout="wide",
)

# Caminhos para ficheiros de dados
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PLANNER_PATH = DATA_DIR / "planner.json"
HISTORY_PATH = DATA_DIR / "history.json"

# Cliente OpenAI (usa a variável de ambiente OPENAI_API_KEY no Streamlit Cloud)
client = OpenAI()

# =========================
# ESTILO PERSONALIZADO
# =========================

PRIMARY_GREEN = "#29c46a"  # usa este para combinar com a imagem do post
ACCENT_YELLOW = "#ffde59"

CUSTOM_CSS = f"""
<style>
:root {{
    --cf-primary: {PRIMARY_GREEN};
    --cf-accent: {ACCENT_YELLOW};
}}

.stApp {{
    background-color: #050509;
}}

.sidebar .stSelectbox label,
.sidebar .stTextInput label,
.sidebar .stNumberInput label {{
    font-weight: 500;
}}

button[kind="primary"], .stButton>button {{
    border-radius: 999px;
    border: none;
    font-weight: 600;
}}

.badge-reco {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 222, 89, 0.12);
    color: #f9e27b;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.8rem;
    border: 1px solid rgba(255, 222, 89, 0.4);
    margin-bottom: 6px;
}}

.badge-reco span.icon {{
    font-size: 0.95rem;
}}

.hashtag-pill {{
    display: inline-block;
    background: #11141a;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 0.78rem;
    margin-right: 4px;
    margin-bottom: 4px;
    border: 1px solid #202632;
}}

.metric-pill {{
    background: #0c1118;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    margin-right: 6px;
}}

.planner-card {{
    background: #0c1118;
    border-radius: 12px;
    padding: 10px 12px;
    border: 1px solid #141a24;
    margin-bottom: 6px;
    font-size: 0.82rem;
}}

.planner-card-title {{
    font-weight: 600;
    margin-bottom: 2px;
}}

.planner-day-header {{
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 8px;
}}

.small-muted {{
    font-size: 0.78rem;
    color: #8891a7;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================
# HELPERS DE DADOS
# =========================

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_planner():
    return load_json(PLANNER_PATH, [])


def save_planner(events):
    save_json(PLANNER_PATH, events)


def load_history():
    return load_json(HISTORY_PATH, [])


def save_history(posts):
    save_json(HISTORY_PATH, posts)


def new_id():
    # id simples baseado em timestamp
    return f"p_{int(datetime.utcnow().timestamp() * 1000)}"


# =========================
# GESTÃO DE SESSÃO
# =========================

def init_session_state():
    today = date.today().isoformat()
    if "gen_date" not in st.session_state:
        st.session_state.gen_date = today
        st.session_state.gen_count = 0
    if st.session_state.gen_date != today:
        st.session_state.gen_date = today
        st.session_state.gen_count = 0

    if "planner_date" not in st.session_state:
        st.session_state.planner_date = today
        st.session_state.planner_added_today = 0
    if st.session_state.planner_date != today:
        st.session_state.planner_date = today
        st.session_state.planner_added_today = 0

    if "anchor_date" not in st.session_state:
        st.session_state.anchor_date = date.today()

    if "last_variations" not in st.session_state:
        st.session_state.last_variations = []
        st.session_state.last_analysis = []


def safe_rerun():
    # compat entre versões de streamlit
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


# =========================
# PROMPT – GERAÇÃO PREMIUM
# =========================

def build_generation_prompt(
    brand, niche, tone, platform, copy_mode, goal, extra, plan
):
    tono_txt = {
        "profissional": "profissional, objetivo mas humano",
        "premium": "premium, elegante, com vocabulário cuidado",
        "emocional": "emocional, próximo e empático",
        "casual": "casual, descontraído, próximo de conversa",
    }.get(tone, "profissional, humano")

    copy_mode_txt = {
        "Venda": "foco máximo em conversão e vendas",
        "Storytelling": "foco em história e construção de relação",
        "Educacional": "foco em ensinar algo útil e prático",
    }.get(copy_mode, "equilíbrio entre valor e vendas")

    pro_level = (
        "Estás no modo PRO: assume que o utilizador é exigente, evita frases vagas, "
        "cria algo que ele consiga literalmente copiar e colar num post real."
        if plan == "Pro"
        else "Estás no modo Starter: mantém uma copy boa mas sem exagerar na complexidade."
    )

    return f"""
Quero que cries VARIAÇÕES de legendas para redes sociais em PT-PT.

Marca: {brand}
Nicho: {niche}
Plataforma: {platform}
Tom de voz: {tono_txt}
Modo de copy: {copy_mode_txt}
Objetivo de hoje: {goal or "não especificado"}
Informação extra relevante: {extra or "nenhuma informação extra"}
Plano: {plan}
{pro_level}

REGRAS MUITO IMPORTANTES:
- NÃO repitas literalmente as frases que o utilizador escreveu no objetivo ou informação extra.
- Usa as ideias, mas reescreve, melhora, aprofunda.
- Frases curtas, respiráveis, fáceis de ler no telemóvel.
- Usa EMOJIS com intenção (no máximo 3–4 por legenda).
- Inclui SEMPRE um CTA claro no fim (ex: "Descobre tudo no site", "Envia mensagem", etc.).
- Adapta o estilo à plataforma (Instagram = mais visual/emocional, TikTok = ritmo e gancho forte).

Quero exatamente 3 variações (A, B, C), cada uma com:
- "titulo": título curto para o Planner (máx. 60 caracteres)
- "legenda": texto completo pronto a colar
- "hashtags": lista com 10 a 15 hashtags relevantes (sem #genérico tipo #love)
- "cta": frase final de chamada à ação (também incluída na legenda)
- "angulo": descrição rápida do ângulo criativo (ex: urgência, bastidores, prova social)

DEVES RESPONDER APENAS EM JSON COM A ESTRUTURA:
{{
  "variacoes": [
    {{
      "id": "A",
      "titulo": "...",
      "legenda": "...",
      "hashtags": ["#exemplo", "..."],
      "cta": "...",
      "angulo": "..."
    }},
    {{ ... B ... }},
    {{ ... C ... }}
  ]
}}
"""


def call_openai_json(prompt: str, model: str = "gpt-4.1-mini", temperature: float = 0.9):
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "És um copywriter sénior de social media a trabalhar para gestores de marca exigentes.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = resp.choices[0].message.content
    return json.loads(content)


# =========================
# ANÁLISE AUTOMÁTICA v8.2
# =========================

def analyse_variations(variations, platform, tone, copy_mode):
    """Devolve lista de dicts com scores por variação."""
    text_blocks = []
    for v in variations:
        text_blocks.append(
            {
                "id": v["id"],
                "titulo": v["titulo"],
                "legenda": v["legenda"],
            }
        )

    prompt = f"""
Quero que analises estas legendas para {platform}.

Tom de voz pretendido: {tone}
Modo de copy: {copy_mode}

Para CADA variação avalia:
- clareza (0-10)
- conversao (0-10) -> potencial de gerar cliques/vendas/mensagens
- engajamento (0-10) -> potencial de gerar comentários, partilhas, saves
- emocao (0-10)
- credibilidade (0-10)
- adequacao_plataforma (0-10)

Depois calcula:
- score_final (0-10) -> média ponderada, com peso maior para conversão e engajamento
- recomendado (true/false) -> se achas que é a melhor opção para usar.

Responde APENAS em JSON:
{{
  "avaliacoes": [
    {{
      "id": "A",
      "clareza": 0,
      "conversao": 0,
      "engajamento": 0,
      "emocao": 0,
      "credibilidade": 0,
      "adequacao_plataforma": 0,
      "score_final": 0,
      "recomendado": false
    }},
    ...
  ]
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "És um analista de performance de social media extremamente exigente e numérico.",
            },
            {"role": "user", "content": json.dumps({"variacoes": text_blocks}, ensure_ascii=False)},
            {"role": "user", "content": prompt},
        ],
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("avaliacoes", [])


# =========================
# LÓGICA DE PLANO
# =========================

def get_plan_limits(plan: str):
    if plan == "Starter":
        return {
            "max_gen_day": 5,
            "max_planner_day": 5,
            "analysis_enabled": False,
        }
    # Pro
    return {
        "max_gen_day": 100,
        "max_planner_day": 999,
        "analysis_enabled": True,
    }


# =========================
# UI – SIDEBAR
# =========================

def sidebar_profile():
    st.sidebar.markdown("### Plano e perfil")

    plan = st.sidebar.selectbox("Plano", ["Starter", "Pro"], index=1)
    limits = get_plan_limits(plan)

    st.sidebar.markdown(
        f"**Gerações hoje:** {st.session_state.gen_count}/{limits['max_gen_day']}"
    )
    st.sidebar.markdown(
        f"**Tarefas no planner hoje:** {st.session_state.planner_added_today}/{limits['max_planner_day']}"
    )

    st.sidebar.markdown("---")

    brand = st.sidebar.text_input("Marca", value="Loukisses")
    niche = st.sidebar.text_input("Nicho/tema", value="Moda feminina")
    tone = st.sidebar.selectbox(
        "Tom de voz",
        ["profissional", "premium", "emocional", "casual"],
        index=1,
    )
    copy_mode = st.sidebar.selectbox(
        "Modo de copy", ["Venda", "Storytelling", "Educacional"], index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Métricas da conta (simuladas por enquanto)")
    st.sidebar.markdown(
        '<span class="small-muted">Integração real fica para o Pro+.</span>',
        unsafe_allow_html=True,
    )

    seguidores = st.sidebar.number_input("Seguidores", value=1200, step=100)
    engaj = st.sidebar.number_input("Engaj. %", value=3.4, step=0.1)
    alcance = st.sidebar.number_input("Alcance médio", value=1400, step=50)

    return plan, brand, niche, tone, copy_mode, seguidores, engaj, alcance


# =========================
# PÁGINA – GERAR
# =========================

def page_generate(plan, brand, niche, tone, copy_mode):
    limits = get_plan_limits(plan)

    st.markdown("## ⚡ Geração inteligente")

    col_goal, col_extra = st.columns([1, 1])
    with col_goal:
        goal = st.text_input(
            "O que queres comunicar hoje?",
            value="Apresentação da nova coleção de Outono",
            max_chars=200,
        )
    with col_extra:
        extra = st.text_area(
            "Informação extra (opcional)",
            value="Desconto de 10% no site até domingo.",
            height=80,
        )

    platform = st.selectbox("Plataforma", ["instagram", "tiktok"], index=0)

    st.markdown("---")

    disabled = st.session_state.gen_count >= limits["max_gen_day"]
    if disabled:
        st.warning(
            "Atingiste o limite de gerações de hoje para o teu plano. "
            "Sobe para Pro ou volta amanhã. 💡"
        )

    if st.button("⚡ Gerar agora", disabled=disabled, type="primary"):
        with st.spinner("A pensar na melhor copy para ti..."):
            prompt = build_generation_prompt(
                brand, niche, tone, platform, copy_mode, goal, extra, plan
            )
            data = call_openai_json(prompt)
            variations = data.get("variacoes", [])
            st.session_state.last_variations = variations

            if limits["analysis_enabled"]:
                analysis = analyse_variations(variations, platform, tone, copy_mode)
                st.session_state.last_analysis = analysis
            else:
                st.session_state.last_analysis = []

        st.session_state.gen_count += 1

    variations = st.session_state.last_variations
    analysis = {a["id"]: a for a in st.session_state.last_analysis}

    if not variations:
        st.info("Gera primeiro conteúdo para veres as variações aqui em baixo. 🙂")
        return

    st.markdown("### Resultados")

    cols = st.columns(3)
    for col, var in zip(cols, variations):
        with col:
            vid = var["id"]
            ana = analysis.get(vid)
            is_reco = bool(ana and ana.get("recomendado"))

            st.markdown(f"**Variação {vid}**")

            if is_reco:
                st.markdown(
                    '<div class="badge-reco"><span class="icon">✨</span> Nossa recomendação</div>',
                    unsafe_allow_html=True,
                )

            st.markdown(f"**Título (para planner):** {var['titulo']}")
            st.write(var["legenda"])

            st.markdown("**Hashtags sugeridas:**")
            tags_html = " ".join(
                f'<span class="hashtag-pill">#{t.lstrip("#")}</span>'
                for t in var.get("hashtags", [])
            )
            st.markdown(tags_html, unsafe_allow_html=True)

            if ana:
                st.markdown("**Análise automática (Pro)**")
                st.markdown(
                    f"""
<span class="metric-pill">🎯 Score: {ana['score_final']:.1f}</span>
<span class="metric-pill">📣 Engaj.: {ana['engajamento']:.1f}</span>
<span class="metric-pill">💶 Conv.: {ana['conversao']:.1f}</span>
""",
                    unsafe_allow_html=True,
                )

            # Adicionar ao planner
            day_default = date.today().isoformat()
            col_dia, col_hora = st.columns(2)
            with col_dia:
                day = st.date_input(
                    "Dia", value=date.today(), key=f"day_{vid}"
                ).isoformat()
            with col_hora:
                time_str = st.time_input(
                    "Hora", value=datetime.strptime("18:00", "%H:%M").time(), key=f"time_{vid}"
                ).strftime("%H:%M")

            if st.button(
                "➕ Adicionar ao planner",
                key=f"add_planner_{vid}",
            ):
                events = load_planner()

                # verificar limite diário
                if st.session_state.planner_added_today >= get_plan_limits(plan)[
                    "max_planner_day"
                ]:
                    st.warning(
                        "Chegaste ao limite diário de entradas no planner para este plano."
                    )
                else:
                    events.append(
                        {
                            "id": new_id(),
                            "day": day,
                            "time": time_str,
                            "platform": platform,
                            "title": var["titulo"],
                            "caption": var["legenda"],
                            "hashtags": var.get("hashtags", []),
                            "score": float(analysis.get(vid, {}).get("score_final", 0))
                            if analysis
                            else None,
                            "status": "planned",
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    )
                    save_planner(events)
                    st.session_state.planner_added_today += 1
                    st.success("Adicionado ao planner ✅")


# =========================
# PÁGINA – PLANNER
# =========================

def week_bounds(anchor: date):
    # semana de segunda a domingo
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def page_planner(plan):
    st.markdown("## 📅 Planner semanal")

    limits = get_plan_limits(plan)

    col_prev, col_next, col_anchor = st.columns([1, 1, 2])
    with col_prev:
        if st.button("« Semana anterior"):
            st.session_state.anchor_date -= timedelta(days=7)
            safe_rerun()
    with col_next:
        if st.button("Próxima semana »"):
            st.session_state.anchor_date += timedelta(days=7)
            safe_rerun()
    with col_anchor:
        anchor_ui = st.date_input(
            "Âncora", value=st.session_state.anchor_date
        )
        if anchor_ui != st.session_state.anchor_date:
            st.session_state.anchor_date = anchor_ui
            safe_rerun()

    anchor = st.session_state.anchor_date
    week_start, week_end = week_bounds(anchor)
    st.markdown(
        f"**Semana de {week_start.strftime('%d/%m')} a {week_end.strftime('%d/%m')}**"
    )

    events = load_planner()
    week_events = [
        e
        for e in events
        if week_start.isoformat() <= e["day"] <= week_end.isoformat()
    ]
    week_events.sort(key=lambda e: (e["day"], e["time"]))

    # mapa dia -> eventos
    by_day = { (week_start + timedelta(days=i)).isoformat(): [] for i in range(7) }
    for e in week_events:
        by_day[e["day"]].append(e)

    cols = st.columns(7)
    day_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    for idx, col in enumerate(cols):
        d = week_start + timedelta(days=idx)
        d_iso = d.isoformat()
        posts = by_day.get(d_iso, [])

        with col:
            st.markdown(
                f'<div class="planner-day-header">{day_labels[idx]}<br><span class="small-muted">{d.strftime("%d/%m")}</span></div>',
                unsafe_allow_html=True,
            )

            if not posts:
                st.markdown('<span class="small-muted">Sem posts.</span>', unsafe_allow_html=True)
                continue

            for e in posts:
                score_txt = (
                    f"{e['score']:.1f}" if isinstance(e.get("score"), (int, float)) else "-"
                )
                st.markdown(
                    f"""
<div class="planner-card">
  <div class="planner-card-title">{e['time']} · {e['platform']}</div>
  <div class="small-muted">{e['title']}</div>
  <div class="small-muted">Score: {score_txt}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

                exp_key = f"exp_{e['id']}"
                with st.expander("Ver detalhes", expanded=False):
                    st.markdown(f"**Legenda:**\n\n{e['caption']}")
                    tags_html = " ".join(
                        f'<span class="hashtag-pill">#{t.lstrip("#")}</span>'
                        for t in e.get("hashtags", [])
                    )
                    st.markdown("**Hashtags:**", unsafe_allow_html=True)
                    st.markdown(tags_html or "–", unsafe_allow_html=True)

                    status = e.get("status", "planned")
                    st.markdown(f"**Estado atual:** `{status}`")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Marcar como concluído", key=f"done_{e['id']}"):
                            e["status"] = "done"
                            # registar no histórico
                            history = load_history()
                            history.append(
                                {
                                    "id": e["id"],
                                    "day": e["day"],
                                    "time": e["time"],
                                    "platform": e["platform"],
                                    "title": e["title"],
                                    "score": e.get("score"),
                                    "completed_at": datetime.utcnow().isoformat(),
                                }
                            )
                            save_history(history)
                            save_planner(events)
                            st.success("Marcado como concluído e enviado para Performance ✅")
                            safe_rerun()
                    with c2:
                        if st.button("🗑 Remover", key=f"del_{e['id']}"):
                            events = [ev for ev in events if ev["id"] != e["id"]]
                            save_planner(events)
                            st.warning("Post removido do planner.")
                            safe_rerun()


# =========================
# PÁGINA – PERFORMANCE
# =========================

def page_performance(plan):
    if plan == "Starter":
        st.markdown("## 📊 Performance")
        st.warning(
            "A aba de performance detalhada é exclusiva do plano **Pro**. "
            "Faz upgrade para ver histórico, scores e resultados. 💹"
        )
        return

    st.markdown("## 📊 Performance (Pro)")

    history = load_history()
    if not history:
        st.info("Ainda não tens posts concluídos. Marca alguns no Planner para ver aqui.")
        return

    history_sorted = sorted(
        history, key=lambda h: (h["day"], h["time"]), reverse=True
    )

    st.markdown("### Resultados concluídos")
    st.dataframe(
        history_sorted,
        use_container_width=True,
        hide_index=True,
    )


# =========================
# PÁGINA – EXPORT
# =========================

def page_export(plan):
    st.markdown("## 📤 Export")

    planner = load_planner()
    if not planner:
        st.info("Não há nada no planner para exportar ainda.")
        return

    # export txt básico para todos os planos
    lines = []
    for e in sorted(planner, key=lambda e: (e["day"], e["time"])):
        lines.append(
            f"{e['day']} {e['time']} · {e['platform']} · {e['title']}\n{e['caption']}\n"
        )
        if e.get("hashtags"):
            tags = " ".join(f"#{t.lstrip('#')}" for t in e["hashtags"])
            lines.append(tags)
        lines.append("\n" + "-" * 40 + "\n")

    txt = "\n".join(lines)
    st.download_button(
        "⬇️ Download .txt",
        data=txt,
        file_name="contentforge_planner.txt",
        mime="text/plain",
    )

    if plan == "Pro":
        # export csv simples no Pro
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["day", "time", "platform", "title", "score", "status"])
        for e in sorted(planner, key=lambda e: (e["day"], e["time"])):
            writer.writerow(
                [
                    e["day"],
                    e["time"],
                    e["platform"],
                    e["title"],
                    e.get("score"),
                    e.get("status", "planned"),
                ]
            )

        st.download_button(
            "⬇️ Download .csv (Pro)",
            data=output.getvalue(),
            file_name="contentforge_planner.csv",
            mime="text/csv",
        )


# =========================
# MAIN
# =========================

def main():
    init_session_state()
    (
        plan,
        brand,
        niche,
        tone,
        copy_mode,
        seguidores,
        engaj,
        alcance,
    ) = sidebar_profile()

    st.markdown("## ContentForge v9.0 🍏")
    st.markdown(
        "Gera conteúdo inteligente, organiza num planner semanal e, no plano Pro, analisa a força de cada publicação."
    )

    tab_gerar, tab_planner, tab_perf, tab_export = st.tabs(
        ["⚡ Gerar", "📅 Planner", "📊 Performance", "📤 Export"]
    )

    with tab_gerar:
        page_generate(plan, brand, niche, tone, copy_mode)
    with tab_planner:
        page_planner(plan)
    with tab_perf:
        page_performance(plan)
    with tab_export:
        page_export(plan)


if __name__ == "__main__":
    main()
