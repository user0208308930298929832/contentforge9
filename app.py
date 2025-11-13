import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

import streamlit as st
from openai import OpenAI

# ---------------- CONFIG BÁSICA ----------------
st.set_page_config(page_title="ContentForge v9.1", layout="wide")

client = OpenAI()  # OPENAI_API_KEY vem das secrets/env


# ---------------- ESTADO INICIAL ----------------
def init_state():
    today = date.today().isoformat()
    if "gen_date" not in st.session_state:
        st.session_state.gen_date = today
        st.session_state.gen_count = 0
    if st.session_state.gen_date != today:
        st.session_state.gen_date = today
        st.session_state.gen_count = 0

    if "planner_events" not in st.session_state:
        # cada evento: {id, day, time, title, platform, caption, hashtags, completed, score}
        st.session_state.planner_events: List[Dict[str, Any]] = []

    if "week_anchor" not in st.session_state:
        st.session_state.week_anchor = date.today()

    if "generated_variations" not in st.session_state:
        st.session_state.generated_variations: List[Dict[str, Any]] = []


init_state()


# ---------------- PLANOS ----------------
PLAN_CONFIG = {
    "Starter": {
        "daily_generations": 5,
        "analysis": False,
        "performance": False,
    },
    "Pro": {
        "daily_generations": 50,
        "analysis": True,
        "performance": True,
    },
}


def get_plan_limits(plan: str) -> Dict[str, Any]:
    return PLAN_CONFIG[plan]


# ---------------- HELPERS GERAIS ----------------
def week_bounds(anchor: date):
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def score_caption(caption: str) -> Dict[str, float]:
    """Pseudo-análise local para o Pro (sem segunda chamada à API)."""
    text = caption.lower()
    length = len(caption)

    has_offer = any(k in text for k in ["desconto", "%", "promo", "oferta"])
    has_cta = any(
        k in text
        for k in ["link na bio", "clica", "envia mensagem", "comenta", "guarda"]
    )
    has_emotion = any(
        k in text for k in ["história", "sonho", "confiança", "incrível", "magia"]
    )

    clareza = 7.0
    if 80 <= length <= 260:
        clareza += 2
    elif length < 60:
        clareza -= 1
    elif length > 400:
        clareza -= 1.5

    conversao = 6.0 + (1.5 if has_offer else 0) + (1.5 if has_cta else 0)
    engaj = 6.0 + (1.5 if has_emotion else 0)
    emocao = 6.0 + (2.0 if has_emotion else 0)
    cred = 7.0
    adequ = 7.0

    def clamp(x: float) -> float:
        return max(0.0, min(10.0, x))

    metrics = {
        "claridade": round(clamp(clareza), 1),
        "conversao": round(clamp(conversao), 1),
        "engajamento": round(clamp(engaj), 1),
        "emocao": round(clamp(emocao), 1),
        "credibilidade": round(clamp(cred), 1),
        "adequacao": round(clamp(adequ), 1),
    }
    final = (
        metrics["conversao"] * 0.3
        + metrics["engajamento"] * 0.25
        + metrics["claridade"] * 0.15
        + metrics["adequacao"] * 0.15
        + metrics["emocao"] * 0.1
        + metrics["credibilidade"] * 0.05
    )
    metrics["score_final"] = round(final, 1)
    return metrics


# ---------------- PROMPT GERAÇÃO ----------------
def build_generation_prompt(
    brand: str,
    niche: str,
    tone: str,
    platform: str,
    copy_mode: str,
    goal: str,
    extra: str,
    plan: str,
) -> str:
    tone_map = {
        "profissional": "profissional, objetivo mas humano",
        "premium": "premium, elegante, linguagem cuidada",
        "emocional": "emocional, próximo e empático",
        "casual": "casual, descontraído, estilo conversa",
    }
    tone_txt = tone_map.get(tone, "profissional, humano")

    mode_map = {
        "Venda": "foco em conversão e vendas",
        "Storytelling": "foco em história e ligação emocional",
        "Educacional": "foco em ensinar algo útil e aplicável",
    }
    mode_txt = mode_map.get(copy_mode, "equilíbrio entre valor e conversão")

    pro_txt = (
        "Estás no modo PRO: o utilizador é exigente, o texto tem de parecer escrito por um copywriter sénior."
        if plan == "Pro"
        else "Estás no modo Starter: mantém texto simples mas profissional."
    )

    return f"""
Quero que cries 3 VARIAÇÕES de legendas em PT-PT para redes sociais.

Marca: {brand}
Nicho: {niche}
Plataforma: {platform}
Tom de voz: {tone_txt}
Modo de copy: {mode_txt}
Objetivo do dia: {goal or "não especificado"}
Informação extra relevante: {extra or "nenhuma informação extra"}
{pro_txt}

Regras:
- NÃO copies literalmente frases do utilizador (especialmente 'quero levar as pessoas ao site'). Reescreve de forma profissional.
- Frases curtas, respiráveis, boas para ler no telemóvel.
- Usa emojis com intenção (máx. 3–4 por legenda).
- Inclui SEMPRE um CTA no fim (mas não repitas o mesmo CTA nas 3 variações).
- Adapta o estilo à plataforma (Instagram = mais visual/emocional).

Para cada variação (A, B, C) devolve:
- "id": "A" ou "B" ou "C"
- "titulo": título curto para o planner (máx. 60 caracteres)
- "legenda": texto completo (inclui o CTA no fim)
- "hashtags": lista com 10–15 hashtags relevantes (sem #love, #insta, etc.)
- "cta": a frase final de chamada à ação
- "angulo": descrição rápida do ângulo (ex: urgência, bastidores, story, prova social)

Formata a resposta EXCLUSIVAMENTE como JSON com esta estrutura:

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
    {{
      "id": "B",
      "titulo": "...",
      "legenda": "...",
      "hashtags": ["#exemplo", "..."],
      "cta": "...",
      "angulo": "..."
    }},
    {{
      "id": "C",
      "titulo": "...",
      "legenda": "...",
      "hashtags": ["#exemplo", "..."],
      "cta": "...",
      "angulo": "..."
    }}
  ]
}}
"""


def call_openai_json(prompt: str) -> Dict[str, Any]:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "És um copywriter sénior de social media que escreve como um humano, em PT-PT.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = resp.choices[0].message.content
    return json.loads(content)


# ---------------- SIDEBAR ----------------
def sidebar_profile():
    st.sidebar.header("Plano e perfil")

    plan = st.sidebar.selectbox("Plano", ["Starter", "Pro"], index=0)
    limits = get_plan_limits(plan)

    st.sidebar.markdown(
        f"**Gerações hoje:** {st.session_state.gen_count}/{limits['daily_generations']}"
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

    return plan, brand, niche, tone, copy_mode


# ---------------- PÁGINA GERAR ----------------
def page_generate(plan: str, brand: str, niche: str, tone: str, copy_mode: str):
    limits = get_plan_limits(plan)

    st.subheader("⚡ Geração inteligente de conteúdo")

    col1, col2 = st.columns(2)
    with col1:
        goal = st.text_input(
            "O que queres comunicar hoje?",
            value="Lançamento da nova coleção de Outono",
        )
    with col2:
        extra = st.text_area(
            "Informação extra (opcional)",
            value="Desconto de 10% no site até domingo.",
            height=70,
        )

    platform = st.selectbox("Plataforma principal", ["Instagram", "TikTok"], index=0)

    can_generate = st.session_state.gen_count < limits["daily_generations"]
    gen_btn = st.button("⚡ Gerar agora", disabled=not can_generate)

    if not can_generate:
        st.info("Atingiste o limite de gerações de hoje para o teu plano.")

    if gen_btn and can_generate:
        with st.spinner("A gerar variações com IA..."):
            prompt = build_generation_prompt(
                brand, niche, tone, platform, copy_mode, goal, extra, plan
            )
            data = call_openai_json(prompt)
            variations = data.get("variacoes", [])

            # Análise local (apenas Pro)
            if limits["analysis"]:
                for v in variations:
                    v["analysis"] = score_caption(v["legenda"])
                best = max(
                    variations,
                    key=lambda v: v["analysis"]["score_final"],
                    default=None,
                )
                if best:
                    best["recommended"] = True

            st.session_state.generated_variations = variations
            st.session_state.gen_count += 1

    variations = st.session_state.generated_variations
    if not variations:
        st.info("Gera conteúdo para veres as variações aqui em baixo.")
        return

    st.markdown("### Resultados")

    cols = st.columns(3)
    for col, var in zip(cols, variations):
        with col:
            vid = var.get("id", "?")
            st.markdown(f"**Variação {vid}**")

            if var.get("recommended"):
                st.markdown("✨ **Nossa recomendação**")

            st.markdown(f"**Título (planner):** {var['titulo']}")
            st.write(var["legenda"])

            st.markdown("**Hashtags:**")
            st.code(" ".join(var.get("hashtags", [])))

            if limits["analysis"] and "analysis" in var:
                a = var["analysis"]
                st.markdown(
                    f"**Análise automática:** "
                    f"Score {a['score_final']}/10 · Engaj. {a['engajamento']}/10 · Conv. {a['conversao']}/10"
                )
            elif not limits["analysis"]:
                st.caption("🔒 Análise automática apenas no Pro.")

            st.markdown("---")
            st.markdown("**Adicionar ao planner**")
            d_col, h_col = st.columns(2)
            with d_col:
                day = st.date_input(
                    "Dia", value=date.today(), key=f"day_{vid}"
                )
            with h_col:
                time_str = st.time_input(
                    "Hora",
                    value=datetime.strptime("18:00", "%H:%M").time(),
                    key=f"time_{vid}",
                ).strftime("%H:%M")

            if st.button("➕ Adicionar", key=f"add_{vid}"):
                st.session_state.planner_events.append(
                    {
                        "id": f"{datetime.utcnow().timestamp()}_{vid}",
                        "day": day.isoformat(),
                        "time": time_str,
                        "title": var["titulo"],
                        "platform": platform,
                        "caption": var["legenda"],
                        "hashtags": var.get("hashtags", []),
                        "completed": False,
                        "score": var.get("analysis", {}).get("score_final")
                        if limits["analysis"]
                        else None,
                    }
                )
                st.success("Adicionado ao planner ✅")


# ---------------- PÁGINA PLANNER (v9.1) ----------------
def page_planner(plan: str):
    st.subheader("📅 Planner semanal")

    # navegação de semanas
    col_prev, col_center, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("« Semana anterior"):
            st.session_state.week_anchor -= timedelta(days=7)
    with col_next:
        if st.button("Semana seguinte »"):
            st.session_state.week_anchor += timedelta(days=7)
    with col_center:
        anchor_ui = st.date_input("Semana de referência", value=st.session_state.week_anchor)
        if anchor_ui != st.session_state.week_anchor:
            st.session_state.week_anchor = anchor_ui

    week_start, week_end = week_bounds(st.session_state.week_anchor)
    st.caption(
        f"Semana de {week_start.strftime('%d/%m')} a {week_end.strftime('%d/%m')}"
    )

    events = st.session_state.planner_events
    days = [week_start + timedelta(days=i) for i in range(7)]
    by_day: Dict[str, List[Dict[str, Any]]] = {d.isoformat(): [] for d in days}
    for ev in events:
        if week_start.isoformat() <= ev["day"] <= week_end.isoformat():
            by_day.setdefault(ev["day"], []).append(ev)

    cols = st.columns(7)
    day_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    for idx, d in enumerate(days):
        d_iso = d.isoformat()
        posts = by_day.get(d_iso, [])
        with cols[idx]:
            # Cabeçalho centrado
            st.markdown(
                f"<div style='text-align:center; font-weight:600;'>{day_labels[idx]}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='text-align:center; color:gray; margin-bottom:8px;'>{d.strftime('%d/%m')}</div>",
                unsafe_allow_html=True,
            )

            if not posts:
                st.markdown(
                    "<div style='text-align:center; font-size:0.8rem; color:#888;'>Sem tarefas</div>",
                    unsafe_allow_html=True,
                )
                continue

            # ordenar por hora
            for ev in sorted(posts, key=lambda e: e["time"]):
                completed = bool(ev.get("completed"))
                bg = "#E8FDF1" if completed else "#f7f7f7"
                status_txt = "Concluído ✅" if completed else "Pendente"
                status_color = "#00c46b" if completed else "#666666"

                card_html = f"""
<div style="
    background:{bg};
    border-radius:12px;
    padding:8px 10px;
    margin:0 auto 8px auto;
    border:1px solid #ddd;
    text-align:left;
    max-width:220px;
">
  <div style="font-size:0.8rem; color:#555;">{ev['time']} · {ev['platform']}</div>
  <div style="font-weight:600; font-size:0.85rem;">{ev['title']}</div>
  <div style="font-size:0.75rem; color:{status_color}; margin-top:4px;">{status_txt}</div>
</div>
"""
                st.markdown(card_html, unsafe_allow_html=True)

                # Detalhes + ações
                with st.expander("Ver detalhes", expanded=False):
                    st.markdown(f"**Legenda:**\n\n{ev['caption']}")
                    if ev.get("hashtags"):
                        st.markdown("**Hashtags:**")
                        st.code(" ".join(ev["hashtags"]))
                    if ev.get("score") is not None:
                        st.markdown(f"**Score previsto:** {ev['score']}/10")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if not completed:
                            if st.button(
                                "✔ Concluir",
                                key=f"done_{ev['id']}",
                            ):
                                # Marca como concluído uma única vez
                                ev["completed"] = True
                                st.success("Tarefa marcada como concluída ✅")
                                st.experimental_rerun()
                        else:
                            st.markdown("Concluído ✅")
                    with col_b:
                        if st.button(
                            "🗑 Remover",
                            key=f"del_{ev['id']}",
                        ):
                            st.session_state.planner_events = [
                                e for e in st.session_state.planner_events if e["id"] != ev["id"]
                            ]
                            st.warning("Tarefa removida.")
                            st.experimental_rerun()


# ---------------- PÁGINA PERFORMANCE ----------------
def page_performance(plan: str):
    st.subheader("📊 Performance (Pro)")

    if not PLAN_CONFIG[plan]["performance"]:
        st.info("🔒 A aba de performance detalhada é exclusiva do plano Pro.")
        return

    completed = [e for e in st.session_state.planner_events if e.get("completed")]
    if not completed:
        st.info("Ainda não tens tarefas concluídas.")
        return

    st.markdown(f"**Total de publicações concluídas:** {len(completed)}")

    scores = [e["score"] for e in completed if isinstance(e.get("score"), (int, float))]
    if scores:
        avg_score = sum(scores) / len(scores)
        st.markdown(f"**Score médio previsto:** {avg_score:.1f}/10")
    else:
        st.caption("Ainda não há scores calculados (gera conteúdo no Pro).")

    st.markdown("---")
    for ev in sorted(completed, key=lambda e: (e["day"], e["time"]), reverse=True):
        linha = f"- {ev['day']} {ev['time']} · {ev['platform']} · **{ev['title']}**"
        if ev.get("score") is not None:
            linha += f" ({ev['score']}/10)"
        st.markdown(linha)


# ---------------- MAIN ----------------
def main():
    plan, brand, niche, tone, copy_mode = sidebar_profile()

    st.title("ContentForge v9.1")
    st.caption(
        "Gera conteúdo com IA, organiza num planner semanal e acompanha a performance (Pro)."
    )

    tab_gen, tab_plan, tab_perf = st.tabs(["⚡ Gerar", "📅 Planner", "📊 Performance"])

    with tab_gen:
        page_generate(plan, brand, niche, tone, copy_mode)
    with tab_plan:
        page_planner(plan)
    with tab_perf:
        page_performance(plan)


if __name__ == "__main__":
    main()
